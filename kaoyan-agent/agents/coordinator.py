"""Bounded coordinator modeled on HelloAgents chapter 13 specialist composition."""

import asyncio
import json
import logging
import re
from time import monotonic

from agents.base import StructuredAgent
from agents.clarification import clarification_options
from agents.guidance import GENERIC_CLARIFICATION, bare_school, bare_school_message, clarification_with_example
from agents.results import ExpertSection, StepContext, contribute, finalize_result
from core.errors import MODEL_FAILURES, InvalidModelOutput, failure_reason
from agents.resolver import PlanResolver, validate_plan
from intents import local_document_plan
from agents.school import SchoolAgent
from agents.learning import LearningAgent
from agents.note import NoteAgent
from agents.planning import (
    admission_requested,
    admission_scope_requested,
    admission_source_answer,
    basic_dialogue,
)
from agents.practice import PracticeAgent
from agents.study import StudyPlannerAgent
from core.runtime import (
    CallBudget,
    execution_budget,
    model_timeout,
    phase_budget,
    step_rules_reason,
    stream_sink,
)
from core.scheduling import MIN_MODEL_SECONDS, schedule_steps
from core.model import prepare_input
from grounding import numbers_supported, verify
from learning import (
    has_scope,
    model_allowed,
    rules_notice,
    safe_learning_context,
)
from prompts import get
from schemas import (
    CombinedAnswer,
    ConversationConditions,
    ConversationRequest,
    ConversationResolution,
    ExpertStep,
    Preferences,
    StudyPlan,
)

log = logging.getLogger(__name__)
ANSWER_LIMIT = 20000
# 2026-11-03: learning, school and study plan can each use one attempt (was 2 in total).
EXPERT_MODEL_LIMIT = 3
EXCERPT_MARK = "\n[该项内容较长，已节选；可单独提问获取完整回答]"


def merge_answers(parts: list[tuple[str, str]]) -> tuple[str, bool]:
    """Join labelled expert answers within the result limit, marking any excerpt."""
    joined = "\n\n".join(label + "\n" + text for label, text in parts)
    if len(joined) <= ANSWER_LIMIT:
        return joined, False
    overhead = sum(len(label) + 1 + len(EXCERPT_MARK) for label, _ in parts) + 2 * (len(parts) - 1)
    budget = ANSWER_LIMIT - overhead
    limits: dict[int, int] = {}
    # Short sections keep their full text; long ones share what remains equally.
    for position, (index, (_, text)) in enumerate(sorted(enumerate(parts), key=lambda row: len(row[1][1]))):
        limits[index] = min(len(text), budget // (len(parts) - position))
        budget -= limits[index]
    return "\n\n".join(
        label + "\n" + (text if len(text) <= limits[index] else text[:limits[index]] + EXCERPT_MARK)
        for index, (label, text) in enumerate(parts)
    ), True


class ConversationCoordinator(StructuredAgent):
    """Resolve a request, execute only its specialists, and merge checked results."""

    async def resolve(
        self, req: ConversationRequest
    ) -> tuple[ConversationRequest, ConversationResolution]:
        """Prefer prepared/local plans; only one model parser can run."""
        return req, await PlanResolver(self.engine).resolve(req)

    async def plan(self, req: ConversationRequest) -> ConversationResolution:
        """Bound parser attempts/time and report actual use across the checkpoint."""
        budget = CallBudget(1)
        token = execution_budget.set(budget)
        timeout_token = model_timeout.set(self.settings.CONVERSATION_PARSE_TIMEOUT)
        try:
            try:
                result = (await asyncio.wait_for(
                    self.resolve(req), timeout=self.settings.CONVERSATION_PARSE_TIMEOUT
                ))[1]
            except TimeoutError:
                result = await PlanResolver(self.engine).resolve(req, allow_model=False)
            result.modelCallsUsed = budget.used
            return result
        finally:
            execution_budget.reset(token)
            model_timeout.reset(timeout_token)

    async def handle(self, req: ConversationRequest) -> dict:
        """Initialize the selected total budget without mutating a live counter."""
        resolution = (
            validate_plan(req.preparedPlan, req) if req.preparedPlan is not None else await self.plan(req)
        )
        # Revalidate the explicit current intent for prepared local-link lookups.
        if resolution.action == "ADMISSION_LINKS":
            _, resolution = await self.resolve(req)
        budget = execution_budget.get()
        token = None
        if req.preparedPlan is None or budget is None:
            token = execution_budget.set(
                CallBudget(
                    4 if resolution.planVersion == 2 else 2, resolution.modelCallsUsed
                )
            )
        try:
            started = monotonic()
            result = await self._execute_resolution(req, resolution)
            options = clarification_options(result, resolution)
            if options:
                result["clarificationOptions"] = options
                finalize_result(result, self.corpus.release_id, "CHAT")
            active_budget = execution_budget.get()
            log.info(
                "conversation outcome=%s mode=%s partial=%s elapsed_ms=%d attempts=%d",
                result["outcome"],
                result.get("explanationMode", "rules"),
                result.get("partial", False),
                int((monotonic() - started) * 1000),
                active_budget.used if active_budget else resolution.modelCallsUsed,
            )
            return result
        finally:
            if token is not None:
                execution_budget.reset(token)

    async def _execute_resolution(
        self, req: ConversationRequest, resolution: ConversationResolution
    ) -> dict:
        """Dispatch a validated single action or bounded specialist plan."""
        resolution = validate_plan(resolution, req)
        if admission_scope_requested(req.userInput):
            return self.finish({
                "outcome": "COMPLETED", "answer": admission_source_answer(),
                "conditions": req.conditions.model_dump(), "explanationMode": "rules",
            })
        if resolution.clarification:
            if resolution.action.startswith("DOCUMENT_"):
                return await self.document((req, resolution))
            return await self.answer((req, resolution))
        if resolution.planVersion == 2 and resolution.steps:
            return await self.collaborate(req, resolution)
        if basic_dialogue(req.userInput):
            return self.finish(
                {
                    "outcome": "COMPLETED",
                    "answer": "你好，我可以帮你学习408知识、分析学情、安排复习和练习、比较院校，以及整理个人笔记。也可以先做可跳过的学情诊断。",
                    "conditions": req.conditions.model_dump(),
                }
            )
        if resolution.action.startswith("DOCUMENT_"):
            return await self.document((req, resolution))
        if resolution.action == "LEARNING_ANALYSIS":
            return await self.learning((req, resolution))
        if resolution.action == "SCHOOL_LOOKUP":
            return self.finish({
                "outcome": "UNSUPPORTED", "explanationMode": "rules",
                "answer": "院校库信息由Java业务服务读取，请通过主助手查询。",
                "conditions": req.conditions.model_dump(),
            })
        return await self.answer((req, resolution))

    async def document(
        self, state: tuple[ConversationRequest, ConversationResolution]
    ) -> dict:
        """Keep the legacy document entrypoint."""
        return await NoteAgent(self).execute(state)

    async def learning(
        self, state: tuple[ConversationRequest, ConversationResolution]
    ) -> dict:
        """Keep the legacy learning entrypoint."""
        expert = PracticeAgent if state[1].operation != "NONE" else LearningAgent
        return await expert(self).execute(state)

    async def collaborate(
        self, req: ConversationRequest, resolution: ConversationResolution
    ) -> dict:
        """Schedule ready experts while keeping display order and model priority stable."""
        self.base(req, resolution)
        sink = stream_sink.get()
        allowance = CallBudget(EXPERT_MODEL_LIMIT)
        phase_token = phase_budget.set(allowance)
        labels = {
            "LEARNING": "学情分析",
            "SCHOOL": "院校比较",
            "KNOWLEDGE": "知识辅导",
            "PRACTICE": "练习建议",
            "NOTE": "笔记建议",
            "STUDY_PLAN": "复习安排",
        }

        external = safe_learning_context(req, plan=resolution)

        def eligible(step: ExpertStep) -> bool:
            if not model_allowed(req, self.settings):
                return False
            if step.agent == "PRACTICE":
                return False
            if step.agent == "NOTE":
                return "STUDY_PLAN" not in step.dependsOn and (req.document is None or has_scope(req, "document"))
            if step.agent == "SCHOOL":
                return has_scope(req, "profile") and req.preferences.explainWithAi
            if step.agent == "LEARNING":
                return any(external.get(key) for key in ("statistics", "items", "documents"))
            if step.agent == "STUDY_PLAN":
                return has_scope(req, "stats") and bool(external.get("statistics"))
            return req.attempt is None or has_scope(req, "wrong")

        def pure_rule(step: ExpertStep) -> bool:
            return step.agent == "PRACTICE" or (
                step.agent == "NOTE" and ("STUDY_PLAN" in step.dependsOn or not eligible(step) or allowance.used >= allowance.limit)
            ) or (step.agent == "STUDY_PLAN" and (not eligible(step) or allowance.used >= allowance.limit))

        async def execute(step: ExpertStep, completed: dict[str, dict]) -> dict:
            if sink:
                await sink({"type": "stage", "stage": "正在处理" + labels[step.agent]})
            return await self._execute_step(req, resolution, step, completed)

        reasons: dict[str, str] = {}
        try:
            completed = await schedule_steps(
                resolution.steps, execute, eligible, pure_rule, allowance,
                self.settings.CONVERSATION_EXPERT_TIMEOUT, self.settings.CONVERSATION_STEP_TIMEOUT,
                MIN_MODEL_SECONDS, reasons,
            )
        finally:
            phase_budget.reset(phase_token)
        for agent, scopes in self.rules_scopes(req).items():
            value = completed.get(agent) or {}
            unexplained = (value.get("outcome") == "COMPLETED" and not value.get("notice")
                           and value.get("explanationMode", "rules") == "rules")
            if unexplained:
                token = step_rules_reason.set(reasons.get(agent))
                try:
                    notice = rules_notice(req, self.settings, scopes)
                finally:
                    step_rules_reason.reset(token)
                if notice:
                    value["notice"] = notice
        sections = [(step.agent, completed[step.agent]) for step in resolution.steps]
        states = [value["outcome"] for _, value in sections]
        result = {
            "conditions": req.conditions.model_dump(),
            "references": [],
            "explanationMode": "rules",
            "outcome": next(
                (
                    status
                    for status in ("COMPLETED", "NEEDS_INPUT", "UNSUPPORTED")
                    if status in states
                ),
                "UNSUPPORTED",
            ),
            "sections": [
                ExpertSection(
                    agent=name,
                    outcome=value["outcome"],
                    explanationMode=value.get("explanationMode", "rules"),
                    fallbackReason=value.get("fallbackReason"),
                    notice=value.get("notice"),
                ).model_dump(exclude_none=True)
                for name, value in sections
            ],
            "partial": "COMPLETED" in states
            and any(state != "COMPLETED" for state in states),
        }
        references: dict[str, dict] = {}
        notices = []
        for name, value in sections:
            for ref in value.get("references", []):
                if ref["id"] in references and references[ref["id"]] != ref:
                    raise ValueError("conflicting_expert_reference")
                references[ref["id"]] = ref
            contribute(result, name, value)
            if value.get("notice"):
                notices.append(value["notice"])
            if value["outcome"] != "COMPLETED":
                notices.append(labels[name] + "尚未完成，请补充条件或资料。")
        if len(references) > 20:
            raise ValueError("too_many_expert_references")
        result["references"] = list(references.values())
        result["answer"], shortened = merge_answers(
            [(labels[name], value["answer"]) for name, value in sections]
        )
        # Rule/private summaries never become a second provider's input.
        if (
            len(sections) >= 2
            and not any(name == "LEARNING" for name, _ in sections)
            and not notices
            and all(value.get("explanationMode") == "ai" for _, value in sections)
            and model_allowed(req, self.settings)
        ):
            token = phase_budget.set(CallBudget(1))
            timeout_token = model_timeout.set(
                self.settings.CONVERSATION_SUMMARY_TIMEOUT
            )
            try:
                prepared = prepare_input(
                    self.settings, get("coordinator_summary"),
                    {"sections": [{"role": name, "answer": value["answer"]} for name, value in sections],
                     "references": [{**ref, "content": ref["excerpt"]} for ref in result["references"]]},
                    CombinedAnswer,
                )
                answer = await asyncio.wait_for(
                    self.model.generate(
                        get("coordinator_summary"),
                        prepared.payload,
                        CombinedAnswer,
                    ),
                    timeout=self.settings.CONVERSATION_SUMMARY_TIMEOUT,
                )
                ids = set(answer.sourceIds)
                if not ids <= set(references):
                    raise InvalidModelOutput("unknown_source")
                # The summary restates validated expert answers; checking it only
                # against reference excerpts rejected nearly every learning or
                # plan sentence. Every sentence must be supported by the union of
                # the answers it was given and the visible evidence.
                basis = {
                    f"section-{index}": {"content": str(row.get("answer", ""))}
                    for index, row in enumerate(prepared.payload.get("sections", []))
                    if isinstance(row, dict)
                }
                basis.update(prepared.sources())
                if verify(answer.answer, list(basis), basis)["status"] != "SUPPORTED":
                    raise InvalidModelOutput("unsupported_summary")
                # Without references nothing else checks the prose: counts and
                # scores must come from the already validated expert answers.
                if not numbers_supported(answer.answer, json.dumps(prepared.payload, ensure_ascii=False)):
                    raise InvalidModelOutput("summary_number_mismatch")
                result.update(answer=answer.answer, explanationMode="ai")
            except MODEL_FAILURES as error:
                log.warning("expert=SUMMARY failure=%s reason=%s", type(error).__name__, failure_reason(error))
                notices.append("综合解释不可用，已保留各项专家结果。")
            finally:
                phase_budget.reset(token)
                model_timeout.reset(timeout_token)
        if shortened and result["explanationMode"] != "ai":
            notices.append("部分专家回答较长，已明确标注节选；可单独提问获取完整回答。")
        if notices:
            # Every notice is a full sentence; joining with "；" would print "。；".
            result["notice"] = "".join(
                text if text.endswith(("。", "！", "？")) else text + "。"
                for text in dict.fromkeys(notices)
            )
        return self.finish(result, resolution)

    async def _execute_step(
        self,
        req: ConversationRequest,
        resolution: ConversationResolution,
        step: ExpertStep,
        completed: dict[str, dict],
    ) -> dict:
        """Pass a private request copy and only explicitly declared typed inputs."""
        token = stream_sink.set(None)
        child_req = req.model_copy(deep=True)
        child_plan = resolution.model_copy(deep=True)
        child_plan.steps = []
        child_plan.planVersion = 1
        child_plan.action = "LEARNING_ANALYSIS"
        if step.agent != "PRACTICE":
            child_plan.operation = "NONE"
        if step.agent != "KNOWLEDGE":
            child_req.attempt = None
        try:
            if step.agent == "SCHOOL":
                child_req.taskType = "SCHOOL_RECOMMEND"
                return await self.engine.run(child_req)
            if step.agent == "KNOWLEDGE":
                child_req.taskType = (
                    "WRONG_QUESTION_TUTOR"
                    if child_req.attempt is not None
                    else "KNOWLEDGE_QA"
                )
                return await self.engine.run(child_req)
            if step.agent == "NOTE":
                document_intent = local_document_plan(req.userInput, req.pageContext, req.document is not None)
                child_plan.action = document_intent.action if document_intent is not None else (
                    "DOCUMENT_UPDATE" if child_req.document else "DOCUMENT_CREATE"
                )
                raw = (
                    completed.get("STUDY_PLAN", {}).get("studyPlan")
                    if "STUDY_PLAN" in step.dependsOn
                    else None
                )
                if "STUDY_PLAN" in step.dependsOn and raw is None:
                    return {
                        "outcome": "UNSUPPORTED",
                        "answer": "上游未提供有效复习计划，未生成笔记建议。",
                        "notice": "上游复习计划缺失。",
                        "explanationMode": "rules",
                        "references": [],
                    }
                dependencies = StepContext(
                    StudyPlan.model_validate(raw) if raw is not None else None
                )
                return await NoteAgent(self, dependencies=dependencies).execute(
                    (child_req, child_plan)
                )
            expert = {
                "LEARNING": LearningAgent,
                "STUDY_PLAN": StudyPlannerAgent,
                "PRACTICE": PracticeAgent,
            }[step.agent]
            return await expert(self).execute((child_req, child_plan))
        finally:
            stream_sink.reset(token)

    @staticmethod
    def rules_scopes(req: ConversationRequest) -> dict[str, list[str]]:
        """Experts whose rule results get a reason notice, with the categories their model input needs.

        LEARNING and NOTE explain themselves; PRACTICE never uses the model.
        """
        scopes = {"STUDY_PLAN": ["stats"], "KNOWLEDGE": ["wrong"] if req.attempt is not None else []}
        if req.preferences.explainWithAi:
            scopes["SCHOOL"] = ["profile"]
        return scopes

    def base(
        self, req: ConversationRequest, resolution: ConversationResolution
    ) -> dict:
        """Apply only explicitly provided condition fields to the current request."""
        conditions = req.conditions.model_dump(exclude_unset=True)
        if not resolution.clarification:
            conditions.update(resolution.conditionPatch.model_dump(exclude_unset=True))
        conditions = ConversationConditions.model_validate(conditions)
        req.conditions = conditions
        # Merge, never rebuild: empty or legacy session conditions must not erase
        # request preferences (explainWithAi) or the profile's exam year.
        preferences = req.preferences.model_dump(exclude_unset=True)
        preferences.update(
            conditions.model_dump(exclude={"examYear"}, exclude_unset=True, exclude_none=True)
        )
        req.preferences = Preferences.model_validate(preferences)
        if conditions.examYear is not None:
            req.profile.examYear = conditions.examYear
        req.userInput = resolution.standaloneQuery
        return conditions.model_dump()

    async def answer(
        self, state: tuple[ConversationRequest, ConversationResolution]
    ) -> dict:
        """Delegate the existing answer branch and preserve its result contract."""
        req, resolution = state
        conditions = self.base(req, resolution)
        if (
            resolution.action == "ADMISSION_LINKS"
            and not resolution.clarification
            and resolution.admissionLinks is not None
            and admission_requested(resolution.standaloneQuery)
        ):
            result = await asyncio.wait_for(
                SchoolAgent(self).execute((req, resolution)),
                timeout=self.settings.CONVERSATION_EXPERT_TIMEOUT,
            )
            if re.search(r"推荐|择校", req.userInput):
                rule_request = req.model_copy(deep=True)
                # Link lookup uses no extra generation: keep the compound school stage bounded.
                rule_request.preferences.explainWithAi = False
                recommendation = await self.engine.schools(rule_request)
                recommendation["answer"] += "\n" + result["answer"]
                if result.get("outcome") != "COMPLETED":
                    recommendation["outcome"] = "UNSUPPORTED"
                    recommendation["notice"] = result.get("notice") or result["answer"]
                if "admissionLinks" in result:
                    recommendation["admissionLinks"] = result["admissionLinks"]
                result = recommendation
        elif resolution.clarification or resolution.action == "CHAT":
            school = None if resolution.clarification else bare_school(req.userInput)
            result = {
                "outcome": "NEEDS_INPUT",
                "answer": resolution.clarification
                or (bare_school_message(school[0]) if school else GENERIC_CLARIFICATION),
                "references": [],
            }
        else:
            req.taskType = (
                resolution.action
                if resolution.action
                in ("KNOWLEDGE_QA", "SCHOOL_RECOMMEND", "WRONG_QUESTION_TUTOR")
                else "CHAT"
            )
            result = await self.engine.run(req)
        result.update(conditions=conditions, standaloneQuery=resolution.standaloneQuery)
        return self.finish(result, resolution)

    def finish(
        self, result: dict, resolution: ConversationResolution | None = None
    ) -> dict:
        """Attach stable metadata and existing missing-input guidance."""
        if result.get("outcome") == "NEEDS_INPUT":
            plan = resolution or ConversationResolution(
                action="LEARNING_ANALYSIS" if result.get("evidence") else "CHAT",
                standaloneQuery=result.get("standaloneQuery") or "请补充条件",
            )
            result["answer"] = clarification_with_example(
                result.get("answer", "请补充请求的对象和条件。"), plan
            )
        return finalize_result(result, self.corpus.release_id, "CHAT")
