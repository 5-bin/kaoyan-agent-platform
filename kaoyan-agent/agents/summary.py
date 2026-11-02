"""HelloAgents domain implementation preserving the existing business rules."""

import json
import logging

from agents.base import StructuredAgent
from core.errors import MODEL_FAILURES, InvalidModelOutput, fallback_reason, failure_reason
from grounding import numbers_supported
from learning import has_scope, model_allowed
from prompts import get
from schemas import ChatRequest, Summary

log = logging.getLogger(__name__)


class SummaryAgent(StructuredAgent):
    """One request-scoped domain expert."""

    async def handle(self, req: ChatRequest) -> dict:
        """Summarize only the supplied graded attempt snapshots."""
        if not req.questions:
            return {"outcome": "NEEDS_INPUT", "answer": "该批次尚无可总结的有效作答。"}
        correct = sum((q.correct for q in req.questions))
        total = len(req.questions)
        weak = sorted(
            {q.knowledgePoint or q.subject for q in req.questions if not q.correct}
        )
        result = {
            "outcome": "COMPLETED",
            "answer": f"有效作答{total}题，正确{correct}题。",
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total * 100, 1),
            "weakPoints": weak,
            "explanationMode": "rules",
        }
        # The wrong scope covers wrong attempts only; correct attempts and their
        # flags would reveal batch statistics without the stats scope.
        statistics = dict(result) if has_scope(req, "stats") else {}
        wrong = [q for q in req.questions if not q.correct] if has_scope(req, "wrong") else []
        if model_allowed(req, self.settings) and (statistics or wrong):
            payload = {
                "statistics": statistics,
                "questions": [
                    {"ref": f"Q{i + 1}", **q.model_dump(exclude={"id"})}
                    for i, q in enumerate(wrong)
                ],
            }
            try:
                answer = await self.model.generate(get("practice_summary"), payload, Summary)
                if not numbers_supported(answer.summary, json.dumps(payload, ensure_ascii=False)):
                    raise InvalidModelOutput("summary_number_mismatch")
                result.update(answer=answer.summary, explanationMode="ai")
            except MODEL_FAILURES as e:
                log.warning("summaryModelFailure=%s reason=%s", type(e).__name__, failure_reason(e))
                result.update(explanationMode="fallback", fallbackReason=fallback_reason(e))
        return result
