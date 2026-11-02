"""HelloAgents domain implementation preserving the existing business rules."""

import logging

from agents.base import StructuredAgent
from core.errors import MODEL_FAILURES, InvalidModelOutput, fallback_reason, failure_reason
from core.model import prepare_input
from grounding import fully_supported, verify
from core.runtime import withhold_model_deltas
from learning import has_scope, model_allowed, model_messages
from prompts import get
from retrieval import mentions, subject_terms
from schemas import Answer, ChatRequest, TutorExplanation

log = logging.getLogger(__name__)


class KnowledgeAgent(StructuredAgent):
    """One request-scoped domain expert."""

    async def handle(self, req: ChatRequest) -> dict:
        """Retrieve versioned knowledge and validate the original answer contract."""
        if req.attempt is not None:
            return await self.tutor(req)
        subject, anchors = subject_terms(req.userInput or "")

        async def search(scope: str | None) -> list:
            # A chunk that shares only weak words ("栈" for "TCP协议栈") is not
            # evidence for the question; it must mention a recognized topic term.
            found = [
                d.metadata["chunk"]
                for d in await self.knowledge_search.ainvoke(
                    {"query": req.userInput, "subject": scope}
                )
            ]
            return [
                d for d in found
                if not anchors or any(
                    mentions(" ".join((d.title, d.content, *d.keywords)), term) for term in anchors
                )
            ]

        docs = await search(subject)
        if not docs and subject:
            docs = await search(None)
        if not docs:
            return {
                "outcome": "UNSUPPORTED",
                "answer": "当前审核资料未覆盖该问题，请缩小问题范围或补充资料。",
            }
        result = {
            "outcome": "COMPLETED",
            "answer": "以下为来源摘要：\n" + "\n".join((d.content for d in docs)),
            "references": [d.reference().model_dump() for d in docs],
            "explanationMode": "rules",
        }
        if model_allowed(req, self.settings):
            try:
                prepared = prepare_input(
                    self.settings,
                    get("zhishi_wenda"),
                    {
                        "input": req.userInput,
                        "messages": model_messages(req),
                        "references": [
                            {**d.reference().model_dump(), "content": d.content} for d in docs
                        ],
                    },
                    Answer,
                )
                with withhold_model_deltas():
                    answer = await self.model.generate(get("zhishi_wenda"), prepared.payload, Answer)
                ids = set(answer.sourceIds)
                claim_ids = {
                    source for claim in answer.claims for source in claim.sourceIds
                }
                if not ids | claim_ids <= {d.id for d in docs}:
                    raise InvalidModelOutput("unknown_source")
                support = verify(
                    answer.answer,
                    list(ids),
                    {key: dict(value, excerpt=value["content"]) for key, value in prepared.sources().items()},
                    claims=[claim.model_dump() for claim in answer.claims] or None,
                    strict=True,
                )
                result["citationSupport"] = support
                # An answer with no checkable conclusion is not evidence of support.
                if not fully_supported(support):
                    result.update(
                        explanationMode="fallback",
                        fallbackReason="EVIDENCE_MISMATCH",
                        notice="模型回答未能与引用原文充分对齐，已保留来源摘要。"
                        if support["status"] != "NOT_CHECKED"
                        else "模型回答缺少可核对的结论，已保留来源摘要。",
                    )
                else:
                    result.update(
                        answer=answer.answer,
                        explanationMode="ai",
                        references=[
                            d.reference().model_dump()
                            for d in docs
                            if d.id in ids | claim_ids
                        ],
                    )
                    if support["status"] == "PARTIAL":
                        result["notice"] = (
                            "部分结论未能与引用原文充分对齐，请核对来源。"
                        )
            except MODEL_FAILURES as e:
                log.warning("qaModelFailure=%s reason=%s", type(e).__name__, failure_reason(e))
                result.update(
                    explanationMode="fallback", fallbackReason=fallback_reason(e),
                    notice="AI解释不可用，已保留来源摘要。",
                )
        return result

    async def tutor(self, req: ChatRequest) -> dict:
        """Explain only an authorized graded snapshot; never change its answer."""
        attempt = req.attempt
        analysis = attempt.analysis or "此版本未保存解析，无法从已有解析解释原因。"
        result = {
            "outcome": "COMPLETED",
            "recordId": attempt.recordId,
            "standardAnswer": attempt.answer,
            "userAnswer": attempt.userAnswer,
            "questionVersion": attempt.version,
            "answer": f"你的选择：{attempt.userAnswer}；此版本标准答案：{attempt.answer}。\n原题解析：{analysis[:3500]}",
            "explanationMode": "rules",
            "notice": "未启用 AI，当前仅展示原题解析，尚未生成个性化解释或追问回答。",
        }
        if self.settings.LLM_ENABLED and not (
            model_allowed(req, self.settings) and has_scope(req, "wrong")
        ):
            result["notice"] = (
                "尚未授权将错题发送给当前模型，仅展示原题解析；请在 Agent 助手的隐私设置中开启模型与错题授权。"
            )
        if model_allowed(req, self.settings) and has_scope(req, "wrong"):
            try:
                output = await self.model.generate(
                    get("wrong_question_tutor"),
                    {
                        "attempt": attempt.model_dump(exclude={"id", "recordId"}),
                        "query": req.userInput,
                        "messages": model_messages(req),
                    },
                    TutorExplanation,
                )
                # Revalidate even a custom provider adapter's output.
                output = TutorExplanation.model_validate(output.model_dump())
                if output.standardAnswer != attempt.answer:
                    raise InvalidModelOutput("standard_answer_mismatch")
                result.update(
                    answer=output.explanation,
                    explanationMode="ai",
                    notice="AI 辅助解释可能有误，标准答案和判分以已保存作答为准。",
                )
            except MODEL_FAILURES as e:
                log.warning("tutorModelFailure=%s reason=%s", type(e).__name__, failure_reason(e))
                result.update(
                    explanationMode="fallback",
                    fallbackReason=fallback_reason(e),
                    notice="AI 解释或追问暂不可用，已保留原题解析，可稍后重试。",
                )
        return result
