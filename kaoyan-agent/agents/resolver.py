"""One bounded plan resolver for conversation and synchronous compatibility callers."""

import logging
import re
from typing import TYPE_CHECKING

from pydantic import ValidationError

from agents.planning import (
    ModelConversationResolution,
    admission_links_plan,
    admission_scope_requested,
    local_orchestration,
    school_lookup_plan,
)
from core.errors import MODEL_FAILURES, InvalidModelOutput, failure_reason
from intents import (
    REGIONS,
    YEAR,
    ConditionExtractor,
    IntentResolver,
    local_document_plan,
    local_learning_plan,
)
from learning import has_scope, model_allowed, model_messages
from prompts import get
from schemas import ChatRequest, ConversationConditions, ConversationRequest, ConversationResolution

if TYPE_CHECKING:
    from workflows import Workflows

log = logging.getLogger(__name__)

SUPPLEMENT_MAX_CHARS = 30
SUPPLEMENT_CONDITIONS = re.compile(
    "|".join(sorted(REGIONS, key=len, reverse=True)) + r"|" + YEAR + r"|(?<!\d)\d{6}(?!\d)|学硕|专硕"
)
# Only connective wording may surround the conditions. Anything else (不、难、同学、
# 交大、数学一、问号…) means the turn says more than a supplement and goes to the model.
SUPPLEMENT_FILLER = re.compile(
    r"只考虑|仅考虑|限定为|限定在|限于|只考|只要|改为|改成|换成|换为|还是|选择|报考|考研|"
    r"优先|都可以|都行|也行|可以|地区|入学|就|只|仅|选|考|要|我|想|吧|的|了|啊|省|市|年|届|"
    r"[\s，,、。；;！!和与或及]"
)


def clarify(plan: ConversationResolution, message: str) -> ConversationResolution:
    """Return an inert clarification; no business reads or steps may execute."""
    return ConversationResolution(
        action=plan.action if plan.action in {"LEARNING_ANALYSIS", "DOCUMENT_CREATE", "DOCUMENT_UPDATE", "ADMISSION_LINKS", "SCHOOL_LOOKUP"} else "CHAT",
        standaloneQuery=plan.standaloneQuery,
        clarification=message, modelCallsUsed=plan.modelCallsUsed,
    )


def validate_plan(
    plan: ConversationResolution, request: ConversationRequest,
) -> ConversationResolution:
    """Reject inconsistent executable plans, including mutated prepared objects."""
    wire = plan.model_dump(by_alias=True)
    wire["conditionPatch"] = plan.conditionPatch.model_dump(by_alias=True, exclude_unset=True)
    plan = ConversationResolution.model_validate(wire)
    names = {step.agent for step in plan.steps}
    if plan.clarification:
        if plan.reads or plan.operation != "NONE" or plan.steps:
            raise InvalidModelOutput("clarification_must_be_inert")
        return plan
    if plan.steps and plan.action not in {"MULTI_AGENT", "STUDY_PLAN"}:
        raise InvalidModelOutput("action_steps_mismatch")
    if plan.action in {"CHAT", "KNOWLEDGE_QA", "SCHOOL_RECOMMEND", "WRONG_QUESTION_TUTOR", "ADMISSION_LINKS", "SCHOOL_LOOKUP"} and plan.reads:
        raise InvalidModelOutput("action_reads_mismatch")
    if plan.action == "SCHOOL_LOOKUP":
        expected = school_lookup_plan(request)
        if expected is None or expected.schoolLookup != plan.schoolLookup or plan.operation != "NONE":
            raise InvalidModelOutput("school_lookup_intent_mismatch")
    elif plan.schoolLookup is not None:
        raise InvalidModelOutput("unexpected_school_lookup")
    if plan.action == "STUDY_PLAN" and "STUDY_PLAN" not in names:
        raise InvalidModelOutput("missing_study_expert")
    if plan.studyDays != 7 and "STUDY_PLAN" not in names:
        raise InvalidModelOutput("study_days_without_study")
    if plan.action == "DOCUMENT_UPDATE" and request.document is None:
        raise InvalidModelOutput("document_snapshot_required")
    document_intent = local_document_plan(request.userInput, request.pageContext, request.document is not None)
    if "NOTE" in names and document_intent is not None and document_intent.action == "DOCUMENT_UPDATE" and request.document is None:
        raise InvalidModelOutput("document_snapshot_required")
    if plan.action == "WRONG_QUESTION_TUTOR" and request.attempt is None:
        raise InvalidModelOutput("attempt_snapshot_required")
    if plan.action == "ADMISSION_LINKS":
        expected = admission_links_plan(request)
        if expected is None or expected.admissionLinks != plan.admissionLinks or plan.admissionLinks is None:
            raise InvalidModelOutput("admission_intent_mismatch")
    elif plan.admissionLinks is not None:
        raise InvalidModelOutput("unexpected_admission_parameters")
    if plan.operation != "NONE":
        if (plan.steps and "PRACTICE" not in names) or (not plan.steps and plan.action != "LEARNING_ANALYSIS"):
            raise InvalidModelOutput("operation_expert_mismatch")
        local = local_learning_plan(request.userInput, request.pageContext)
        if local is None or local.operation != plan.operation:
            raise InvalidModelOutput("operation_not_requested")
        required_read = {"wrong": "wrong", "favorite": "favorite", "normal": "questions"}.get(plan.target)
        if required_read is not None and required_read not in plan.reads:
            raise InvalidModelOutput("operation_read_mismatch")
        if not plan.reads:
            raise InvalidModelOutput("operation_requires_reads")
    if len(plan.reads) != len(set(plan.reads)):
        raise InvalidModelOutput("duplicate_reads")
    return plan


class PlanResolver:
    """Compose application rules and the one optional HelloAgents model parser."""

    def __init__(self, engine: "Workflows") -> None:
        """Reuse immutable resources and the application's only model adapter."""
        self.engine = engine
        self.keywords = tuple(
            word for doc in engine.corpus.documents if doc.domain == "knowledge"
            for word in doc.keywords
        )

    def condition_supplement(self, text: str) -> bool:
        """Return whether a short turn only supplies school conditions.

        Such turns (“学硕”、“081200学硕”、“只考虑江苏”) are fully covered by the
        deterministic extractor. Questions, negations, references, other
        capabilities and conflicting choices still go to the bounded model parser.
        """
        text = text.strip()
        if not text or len(text) > SUPPLEMENT_MAX_CHARS or ConditionExtractor.conflicting(text):
            return False
        if SUPPLEMENT_FILLER.sub("", SUPPLEMENT_CONDITIONS.sub("", text)):
            return False
        if IntentResolver.fallback_action(text, self.keywords) != "SCHOOL_RECOMMEND":
            return False
        return bool(ConditionExtractor.extract(text).model_fields_set)

    def fallback(self, req: ConversationRequest) -> ConversationResolution:
        """Resolve explicit conditions and bounded historical references locally."""
        text = req.userInput
        action = IntentResolver.fallback_action(text, self.keywords)
        # Only school turns may change session conditions.
        patch = ConditionExtractor.extract(text) if action == "SCHOOL_RECOMMEND" else ConversationConditions()
        clarification = None
        if any(word in text for word in ("它们", "它的", "上述", "刚才")):
            previous = next((
                message.content for message in reversed(req.messages)
                if message.role == "user" and (
                    not model_allowed(req, self.engine.settings)
                    or message.scopes is not None and set(message.scopes) <= set(req.privacy.scopes)
                )
            ), None)
            if previous:
                text = (previous + "；追问：" + text)[-8000:]
                action = "KNOWLEDGE_QA" if action == "CHAT" else action
            else:
                clarification = "请说明你指的是哪个知识点或哪份文档。"
        if ConditionExtractor.conflicting(req.userInput):
            clarification = "本轮出现多个年份或学位条件，请明确希望采用的条件。"
        return ConversationResolution(
            action=action, standaloneQuery=text, conditionPatch=patch,
            clarification=clarification,
        )

    async def resolve(
        self, req: ConversationRequest, *, allow_model: bool = True,
    ) -> ConversationResolution:
        """Validate prepared plans or build one plan, without model retries."""
        if req.preparedPlan is not None:
            return validate_plan(req.preparedPlan, req)
        try:
            return await self._build(req, allow_model=allow_model)
        except (InvalidModelOutput, ValidationError) as error:
            # A locally built plan that fails its own post-conditions asks for
            # clarification instead of turning ordinary input into a 503.
            log.warning("localPlanInvalid=%s", type(error).__name__)
            return ConversationResolution(
                action="CHAT", standaloneQuery=req.userInput,
                clarification="未能确定本轮请求的对象或条件，请换一种说法或补充具体对象。",
            )

    async def _build(
        self, req: ConversationRequest, *, allow_model: bool,
    ) -> ConversationResolution:
        """Build and validate one new plan from local rules or one model parse."""
        if admission_scope_requested(req.userInput):
            return ConversationResolution(action="CHAT", standaloneQuery=req.userInput)
        local = local_orchestration(req)
        if local is None and req.attempt is not None:
            local = ConversationResolution(action="WRONG_QUESTION_TUTOR", standaloneQuery=req.userInput)
        if local is None:
            local = IntentResolver.local_plan(req.userInput, req.pageContext, req.document is not None)
        if local is None and self.condition_supplement(req.userInput):
            # A generic model clarification must not discard explicit conditions.
            local = self.fallback(req)
        if local is None and allow_model and model_allowed(req, self.engine.settings):
            try:
                parsed = await self.engine.model.generate(
                    get("conversation_resolver_0"),
                    {
                        "input": req.userInput, "messages": model_messages(req),
                        "conditions": req.conditions.model_dump() if has_scope(req, "profile") else {},
                        "selectedDocument": {
                            "ref": "D1", "title": req.document.title,
                            "contentAvailable": True, "version": req.document.version,
                        } if req.document and has_scope(req, "document") else None,
                    },
                    ModelConversationResolution, router=True,
                )
                local = parsed
                if local.operation != "NONE":
                    raise InvalidModelOutput("model_operation_forbidden")
                if local.clarification:
                    local = clarify(local, local.clarification)
                local = validate_plan(local, req)
            except MODEL_FAILURES as error:
                log.warning("planFailure=%s reason=%s", type(error).__name__, failure_reason(error))
                local = self.fallback(req)
        if local is None:
            local = self.fallback(req)
        if local.action == "DOCUMENT_UPDATE" and req.document is None:
            local = clarify(local, "请先选择要修改的个人笔记。")
        document_intent = local_document_plan(req.userInput, req.pageContext, req.document is not None)
        if any(step.agent == "NOTE" for step in local.steps) and document_intent is not None and document_intent.action == "DOCUMENT_UPDATE" and req.document is None:
            local = clarify(document_intent, "请先选择要修改的个人笔记。")
        if local.clarification:
            local = clarify(local, local.clarification)
        return validate_plan(local, req)

    async def legacy(self, req: ChatRequest, *, allow_model: bool) -> str:
        """Project a unified plan into the capabilities of the old sync endpoint."""
        conversation = ConversationRequest.model_validate(req.model_dump())
        plan = await self.resolve(conversation, allow_model=allow_model)
        return plan.action if not plan.clarification and not plan.steps and plan.action in {
            "KNOWLEDGE_QA", "SCHOOL_RECOMMEND",
        } else "CHAT"
