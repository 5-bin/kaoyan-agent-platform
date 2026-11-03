"""HelloAgents domain implementation preserving the existing business rules."""

import logging
import re

from agents.base import StructuredAgent
from agents.learning_result import local_learning_result
from agents.learning_validation import validate_enrichment
from core.errors import MODEL_FAILURES, InvalidModelOutput, ToolUnavailable, fallback_reason, failure_reason
from core.model import prepare_input
from core.runtime import withhold_model_deltas
from core.mcp_runtime import McpCallError
from learning import (
    LearningAnswer,
    learning_scopes,
    model_allowed,
    model_messages,
    rule_learning_answer,
    rules_notice,
    safe_learning_context,
    weak_point_topics,
)
from prompts import get
from schemas import (
    ConversationRequest,
    ConversationResolution,
)


log = logging.getLogger(__name__)
TOPIC_LIMIT = 5
TOPIC_PARTS = re.compile(r"[-—、/／与和及]")


def mentions_topic(doc: object, topics: list[str]) -> bool:
    """Keep a reviewed chunk only when its title or text names a selected topic or topic part.

    Without topics (plain user input queries) every result is kept, as before.
    """
    if not topics:
        return True
    text = f"{getattr(doc, 'title', '')} {getattr(doc, 'content', '')}"
    terms = {
        part.strip()
        for topic in topics
        for part in [topic, *TOPIC_PARTS.split(topic)]
        if len(part.strip()) >= 2
    }
    return any(term in text for term in terms)


class LearningAgent(StructuredAgent):
    """One request-scoped domain expert."""

    async def handle(
        self, state: tuple[ConversationRequest, ConversationResolution]
    ) -> dict:
        """Analyze authorized learning snapshots or return controlled operation advice."""
        req, resolution = state
        conditions = self.base(req, resolution)
        local, result, stop = local_learning_result(req, resolution, conditions)
        if stop:
            return result
        if resolution.operation != "NONE":
            raise ValueError("learning_operation_requires_practice")
        rule_answer = result["answer"]
        external = safe_learning_context(req, plan=resolution)
        items = local.get("items", [])
        if (
            not resolution.clarification
            and re.search("(?:加入|添加).{0,10}错题本", req.userInput)
            and items
            and all((item.get("inWrongBook") for item in items))
        ):
            result["answer"] = (
                "所列题目已在你的错题本中，无需重复添加；不会增加错误作答次数。\n"
                + rule_learning_answer(local, resolution)
            )
            return result
        docs = []
        if not resolution.clarification:
            topics = list(
                dict.fromkeys(
                    str(item.get("knowledgePoint") or item.get("subject"))[:100]
                    for item in external.get("items", [])
                    if item.get("knowledgePoint") or item.get("subject")
                )
            )
            topics.extend(
                weak_point_topics(
                    external.get("statistics", {}).get("knowledgePoints", [])
                )
            )
            topics = list(dict.fromkeys(topics))[:TOPIC_LIMIT]
            query = " ".join(topics)[:2000] or req.userInput[:1000]
            try:
                found = await self.engine.knowledge_search.ainvoke({"query": query})
                docs = [
                    item.metadata["chunk"]
                    for item in found[:5]
                    if mentions_topic(item.metadata["chunk"], topics)
                ]
                if docs:
                    result["references"] = [
                        doc.reference().model_dump() for doc in docs
                    ]
                    # Excerpts are shown once under the references panel, not repeated in the body.
                    result["answer"] += (
                        f"\n相关审核资料{len(docs)}条（用于概念复习，不代替本题历史答案），见下方“查看依据”："
                        + "、".join(doc.title for doc in docs)
                        + "。"
                    )
            except (McpCallError, ToolUnavailable, TimeoutError) as error:
                log.warning("learningRetrievalFailure=%s", type(error).__name__)
                result["notice"] = (
                    "相关审核资料检索暂时不可用，已保留本地学习记录摘要。"
                )
        if (
            not resolution.clarification
            and model_allowed(req, self.engine.settings)
            and any((external.get(key) for key in ("statistics", "items", "documents")))
        ):
            try:
                prepared = prepare_input(
                    self.settings,
                    get("learning_expert_0"),
                    {
                        "input": req.userInput,
                        "messages": model_messages(req),
                        "learningContext": external,
                        "references": [
                            {**doc.reference().model_dump(), "content": doc.content} for doc in docs
                        ],
                    },
                    LearningAnswer,
                )
                with withhold_model_deltas():
                    answer = await self.engine.model.generate(get("learning_expert_0"), prepared.payload, LearningAnswer)
                enrichment = validate_enrichment(answer, prepared)
                final_answer = rule_answer + "\n\n" + "\n".join(enrichment.lines)
                if len(final_answer) > 20000:
                    raise InvalidModelOutput("learning_output_too_long")
                result.update(
                    answer=final_answer,
                    explanationMode="ai",
                    citationSupport=enrichment.citation_support,
                    references=[
                        doc.reference().model_dump()
                        for doc in docs
                        if doc.id in enrichment.source_ids
                    ],
                )
            except MODEL_FAILURES as error:
                log.warning("learningModelFailure=%s reason=%s", type(error).__name__, failure_reason(error))
                result.update(
                    explanationMode="fallback",
                    fallbackReason=fallback_reason(error),
                    notice="AI分析不可用，已保留本地记录摘要。",
                )
        elif not resolution.clarification:
            # State the actual blocker (consent, provider, category, budget or time).
            result.setdefault(
                "notice", rules_notice(req, self.engine.settings, learning_scopes(resolution))
                or "本轮使用规则学情结果，未追加模型请求。"
            )
        return result
