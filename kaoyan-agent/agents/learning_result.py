"""Shared deterministic projection for learning reads and practice proposals."""

from learning import rule_learning_answer, safe_learning_context
from schemas import ConversationRequest, ConversationResolution


def local_learning_result(
    request: ConversationRequest,
    plan: ConversationResolution,
    conditions: dict,
) -> tuple[dict, dict, bool]:
    """Return local evidence, result and whether enrichment must stop."""
    local = safe_learning_context(request, external=False, plan=plan)
    result = {
        "outcome": "NEEDS_INPUT" if plan.clarification else "COMPLETED",
        "answer": plan.clarification or rule_learning_answer(local, plan),
        "conditions": conditions,
        "standaloneQuery": plan.standaloneQuery,
        "evidence": local.get("evidence", []),
        "explanationMode": "rules",
    }
    for key in ("notice", "retrievalStatus"):
        if local.get(key):
            result[key] = local[key]
    for key in ("total", "readCount"):
        if key in local:
            result[key] = local[key]
    status = local.get("retrievalStatus")
    if not plan.clarification and status in {
        "BUILDING",
        "BUSY",
        "FAILED",
        "UNAVAILABLE",
    }:
        result.update(
            outcome="UNSUPPORTED",
            answer=local.get("notice", "题目检索暂时不可用，请稍后重试。"),
        )
    stop = bool(plan.clarification) or status in {
        "BUILDING",
        "BUSY",
        "FAILED",
        "UNAVAILABLE",
    }
    return local, result, stop or (status == "READY" and not local.get("items"))
