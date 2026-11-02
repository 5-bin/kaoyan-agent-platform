"""HelloAgents domain implementation preserving the existing business rules."""

import logging
from collections import Counter

from agents.base import StructuredAgent
from core.errors import MODEL_FAILURES, InvalidModelOutput, fallback_reason, failure_reason
from core.model import prepare_input
from core.admission_contract import AdmissionLinksResult
from core.mcp_runtime import McpCallError, McpErrorCode
from grounding import aggregate, verify
from learning import has_scope, model_allowed, model_messages
from prompts import get
from schemas import (
    AdmissionLinksQuery,
    ChatRequest,
    ConversationRequest,
    ConversationResolution,
    Explanations,
    Preferences,
    Profile,
)
from tools.schools import school_tools

log = logging.getLogger(__name__)


DEGREE_LABELS = {"academic": "学硕", "professional": "专硕"}


class SchoolAgent(StructuredAgent):
    """One request-scoped domain expert."""

    def explain_empty(
        self, profile: Profile, pref: Preferences, majors: list[str], excluded: list[dict]
    ) -> tuple[str, list[str]]:
        """Summarize why no program of the exam year passed the hard filters.

        Returns the answer and follow-up hints; it never replaces the user's major
        or year, it only names the conditions that conflict in the current data.
        """
        year = profile.examYear
        same_year = [p for p, _ in self.programs if p.year == year]
        if not same_year:
            return f"当前资料没有{year}年的招生项目，未替换为往年数据。", []
        ids = {p.programId for p in same_year}
        reasons = Counter(
            reason
            for row in excluded
            if row["programId"] in ids
            for reason in row["reasons"]
        )
        degree = DEGREE_LABELS.get(pref.degreeType or "", "未选学位类型")
        answer = (
            f"{year}年资料共{len(same_year)}个项目，均未满足当前条件。排除原因："
            + "、".join(f"{reason}{count}个" for reason, count in reasons.most_common())
            + f"（同一项目可有多项原因）；当前条件为专业{'/'.join(majors)}、{degree}，未替换为往年数据。"
        )
        hints = []
        offered = sorted(
            {(p.majorCode, p.major) for p in same_year if p.degreeType == pref.degreeType}
        )
        if offered and not any(code in majors for code, _ in offered):
            names = "、".join(f"{code}（{name}）" for code, name in offered)
            other = "学硕" if pref.degreeType == "professional" else "专硕"
            hints.append(
                f"资料中{year}年的{degree}专业为{names}，与当前专业条件不同；如需比较请改为该专业代码，或改选{other}。"
            )
        return answer, hints

    async def check_links(self, query: AdmissionLinksQuery) -> dict:
        """Use only the native registered MCP tool; never fall back to local links."""
        if self.engine.admission_links is None:
            return {
                "outcome": "UNSUPPORTED",
                "answer": "招生官网链接查询尚未启用，请联系维护者启用后重试。",
                "notice": "招生链接 MCP 未启用。",
                "references": [],
                "explanationMode": "rules",
            }
        try:
            result = await self.engine.admission_links.ainvoke(query.model_dump())
        except (McpCallError, TimeoutError) as error:
            messages = {
                McpErrorCode.START_FAILED: "招生链接工具启动失败，请联系维护者检查后重启Agent。",
                McpErrorCode.CATALOG_CHANGED: "招生链接工具清单不符合约定，已停用；请联系维护者。",
                McpErrorCode.SCHEMA_CHANGED: "招生链接工具接口不符合约定，已停用；请联系维护者。",
                McpErrorCode.CONNECTION_CLOSED: "招生链接工具连接不可用，请稍后重试或联系维护者。",
                McpErrorCode.TIMEOUT: "招生链接查询超时，本轮未完成；请稍后重试。",
                McpErrorCode.CALL_LIMIT: "本轮招生链接查询已达到一次调用上限，请下一轮明确查询。",
                McpErrorCode.TOOL_FAILED: "招生链接工具执行失败，请稍后重试。",
                McpErrorCode.RESULT_INVALID: "招生链接结果未通过校验，已拒绝使用。",
            }
            message = (
                messages.get(error.code, "招生链接处理失败，请稍后重试。")
                if isinstance(error, McpCallError)
                else "招生链接查询未完成，请稍后重试。"
            )
            return {
                "outcome": "UNSUPPORTED",
                "answer": message,
                "notice": message,
                "references": [],
                "explanationMode": "rules",
            }
        links = AdmissionLinksResult.model_validate(result)
        return {
            "outcome": "COMPLETED",
            "answer": (
                f"已找到{links.schoolName}登记的招生官网链接（登记年份 {links.registeredYear}）；"
                "请自行确认招生年份、专业及报考条件。"
            ),
            "admissionLinks": links.model_dump(mode="json"),
            "references": [],
            "explanationMode": "rules",
        }

    async def handle(
        self, req: ChatRequest | tuple[ConversationRequest, ConversationResolution]
    ) -> dict:
        """Apply unchanged admission constraints and optionally explain verified candidates."""
        if isinstance(req, tuple):
            request, resolution = req
            if resolution.admissionLinks is None:
                raise ValueError("ADMISSION_LINKS_REQUIRED")
            return await self.check_links(resolution.admissionLinks)
        profile, pref = (req.profile, req.preferences)
        majors = pref.majorCodes or []
        if not majors and profile.targetMajor:
            majors = sorted(
                {
                    p.majorCode
                    for p, _ in self.programs
                    if profile.targetMajor in {p.majorCode, p.major}
                }
            )
        missing = []
        if not profile.examYear:
            missing.append("请在个人档案填写报考年份")
        if not majors:
            missing.append("请选择目标专业代码（首批081200、085404）")
        if not pref.degreeType:
            missing.append("请选择学硕或专硕")
        if missing:
            return {
                "outcome": "NEEDS_INPUT",
                "answer": "推荐条件尚不完整。",
                "followUp": missing,
                "candidates": [],
                "unverifiedCandidates": [],
            }
        registry = school_tools(self.programs)
        selection = await registry.execute_async(
            "filter_programs",
            {"profile": profile.model_dump(), "preferences": pref.model_dump()},
        )
        excluded = selection["excluded"]
        selected = await registry.execute_async(
            "rank_programs", {"rows": selection["accepted"]}
        )
        candidates = [row[2] for row in selected]
        empty_answer, empty_hints = self.explain_empty(profile, pref, majors, excluded)
        result = {
            "outcome": "COMPLETED" if candidates else "UNSUPPORTED",
            "answer": "以下为满足条件的候选清单，不代表录取概率。"
            if candidates
            else empty_answer,
            "candidates": candidates,
            "unverifiedCandidates": [],
            "excluded": excluded,
            "references": [row[3].reference().model_dump() for row in selected],
            "explanationMode": "rules",
            "profileSnapshot": profile.model_dump(),
            "preferences": pref.model_dump(),
            "coverage": "、".join(sorted({p.school for p, _ in self.programs}))
            + "；年份："
            + "、".join((str(y) for y in sorted({p.year for p, _ in self.programs})))
            + "；专业："
            + "/".join(sorted({p.majorCode for p, _ in self.programs})),
        }
        if not candidates and empty_hints:
            result["followUp"] = empty_hints
        if req.learningSnapshot is not None:
            result["learningSnapshot"] = req.learningSnapshot.model_dump()
            result["resultSchemaVersion"] = 2
        if (
            candidates
            and pref.explainWithAi
            and model_allowed(req, self.settings)
            and has_scope(req, "profile")
        ):
            try:
                prepared = prepare_input(
                    self.settings,
                    get("tuijian_yuanxiao"),
                    {
                        "input": req.userInput,
                        "messages": model_messages(req),
                        "profile": profile.model_dump(exclude={"background"})
                        if has_scope(req, "profile")
                        else {},
                        "learningSnapshot": req.learningSnapshot.model_dump()
                        if req.learningSnapshot is not None and has_scope(req, "stats")
                        else {},
                        "candidates": candidates,
                        "sources": [
                            {**row[3].reference().model_dump(), "content": row[3].content}
                            for row in selected
                        ],
                    },
                    Explanations,
                )
                answer = await self.model.generate(get("tuijian_yuanxiao"), prepared.payload, Explanations)
                mapping = {e.programId: e for e in answer.explanations}
                if len(mapping) != len(answer.explanations) or set(mapping) != {
                    c["programId"] for c in candidates
                }:
                    raise InvalidModelOutput("candidate_mismatch")
                for c in candidates:
                    if not set(mapping[c["programId"]].sourceIds) <= set(
                        c["sourceIds"]
                    ):
                        raise InvalidModelOutput("unknown_source")
                by_id = {key: dict(value, excerpt=value["content"]) for key, value in prepared.sources("sources").items()}
                items = []
                adopted = 0
                for c in candidates:
                    explanation = mapping[c["programId"]]
                    item = verify(explanation.text, list(explanation.sourceIds), by_id)
                    c["citationSupport"] = item
                    items.append(item)
                    # Admission facts are high risk: unchecked or unsupported prose
                    # never replaces the rule explanation of a candidate.
                    if item["status"] in {"SUPPORTED", "PARTIAL"}:
                        c["explanation"] = explanation.text
                        adopted += 1
                result["citationSupport"] = aggregate(items)
                if not adopted:
                    result.update(
                        explanationMode="fallback",
                        fallbackReason="EVIDENCE_MISMATCH",
                        notice="AI解释未能与招生资料原文充分对齐，已保留规则候选说明。",
                    )
                else:
                    result["explanationMode"] = "ai"
                    if adopted < len(candidates):
                        result["notice"] = (
                            "部分AI解释未能与招生资料原文充分对齐，相应候选保留规则说明，请以来源为准。"
                        )
                    elif result["citationSupport"]["status"] != "SUPPORTED":
                        result["notice"] = (
                            "部分解释未能与招生资料原文充分对齐，请核对来源。"
                        )
            except MODEL_FAILURES as e:
                log.warning("schoolModelFailure=%s reason=%s", type(e).__name__, failure_reason(e))
                result.update(
                    explanationMode="fallback",
                    fallbackReason=fallback_reason(e),
                    notice="AI解释不可用，规则候选及来源已保留。",
                )
        return result
