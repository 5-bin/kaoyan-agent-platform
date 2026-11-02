"""Authorized HelloAgents GSSC with deterministic, offline context budgeting."""

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

from core.errors import ModelUnavailable
from core.framework import ContextBuilder, ContextConfig, ContextPacket, Message
from core.tokens import TokenCounter

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
log = logging.getLogger(__name__)


def wire_json(value: object) -> str:
    """Serialize identically at every budget boundary."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class PreparedModelInput:
    """Isolated provider input and exact visible evidence, never shared by requests."""

    messages: list[dict[str, str]]
    payload: dict[str, JsonValue]
    estimated_tokens: int
    counting_mode: str
    removed_history: int
    shortened_excerpts: int
    removed_statistics: int

    def sources(self, key: str = "references") -> dict[str, dict[str, JsonValue]]:
        """Index evidence actually included in this generation."""
        rows = self.payload.get(key, [])
        return {str(row["id"]): row for row in rows if isinstance(row, dict) and "id" in row} if isinstance(rows, list) else {}


class AuthorizedContextBuilder(ContextBuilder):
    """Collect, select, organize and trim granted inputs without model summaries."""

    def __init__(self, max_tokens: int = 12000, counter: TokenCounter | None = None) -> None:
        """Avoid the framework constructor's cold tokenizer network download."""
        self.memory_tool = self.rag_tool = None
        self.counter = counter or TokenCounter()
        self.config = ContextConfig(max_tokens=max_tokens, reserve_ratio=0, min_relevance=0, enable_compression=True)
        self.removed_history = self.shortened_excerpts = self.removed_statistics = 0

    def prepare(self, instruction: str, payload: dict[str, JsonValue]) -> PreparedModelInput:
        """Run native GSSC over a serialized copy, rejecting mandatory overflow."""
        self.removed_history = self.shortened_excerpts = self.removed_statistics = 0
        messages = json.loads(self.build(user_query=wire_json(payload), system_instructions=instruction))
        result = PreparedModelInput(messages, json.loads(messages[1]["content"]), self._count(messages), self.counter.mode,
                                    self.removed_history, self.shortened_excerpts, self.removed_statistics)
        log.info("context mode=%s estimated_tokens=%d history_removed=%d excerpts_shortened=%d statistics_removed=%d",
                 result.counting_mode, result.estimated_tokens, result.removed_history, result.shortened_excerpts, result.removed_statistics)
        return result

    def messages(self, instruction: str, payload: dict[str, JsonValue]) -> list[dict[str, str]]:
        """Compatibility projection of the system and JSON data messages."""
        return self.prepare(instruction, payload).messages

    def _count(self, messages: list[dict[str, str]]) -> int:
        return self.counter.count(wire_json(messages)) + 16

    def _gather(self, user_query: str, conversation_history: list[Message], system_instructions: str | None,
                additional_packets: list[ContextPacket]) -> list[ContextPacket]:
        """Collect authorized top-level fields without extra private retrieval."""
        packets = [ContextPacket(content=system_instructions or "", token_count=max(1, self.counter.count(system_instructions or "")), metadata={"type": "instructions"})]
        for key, value in json.loads(user_query).items():
            content = wire_json(value)
            packets.append(ContextPacket(content=content, token_count=max(1, self.counter.count(content)), metadata={"type": "data", "key": key}))
        return packets

    def _select(self, packets: list[ContextPacket], user_query: str) -> list[ContextPacket]:
        """Rank granted candidates; never use relevance to discard safety fields."""
        payload = json.loads(user_query)
        query = str(payload.get("input", payload.get("instruction", payload.get("query", ""))))
        selected = []
        for packet in packets:
            if packet.metadata["type"] in {"instructions", "data"}:
                packet.relevance_score = self._relevance(query, packet.content)
                selected.append(packet)
        # The structured payload keeps its stable field order. Within reducible
        # collections, _compress selects excerpts/rows using the same relevance.
        return selected

    def _structure(self, selected_packets: list[ContextPacket], user_query: str, system_instructions: str | None) -> str:
        """Keep trusted instructions separate from all untrusted data."""
        payload = {packet.metadata["key"]: json.loads(packet.content) for packet in selected_packets if packet.metadata["type"] == "data"}
        return wire_json([Message(content=system_instructions or "", role="system").to_dict(), Message(content=wire_json(payload), role="user").to_dict()])

    def _compress(self, context: str) -> str:
        """Trim history, retrieved prose, then statistical rows; never raw JSON."""
        messages = json.loads(context)
        payload = json.loads(messages[1]["content"])

        def fits() -> bool:
            messages[1]["content"] = wire_json(payload)
            return self._count(messages) <= self.config.max_tokens

        if fits():
            return wire_json(messages)
        payload["contextNotice"] = "上下文为本轮授权节选；未展示明细不代表不存在，统计总量与样本口径保持原值。"
        history = payload.get("messages", [])
        while not fits() and history:
            history.pop(0)
            self.removed_history += 1
        query = str(payload.get("input", payload.get("instruction", payload.get("query", ""))))
        excerpts: list[tuple[dict[str, JsonValue], str]] = []
        # Qualification prose, graded snapshots and full personal documents are
        # indivisible. Only explicit retrieved evidence prose can be shortened.
        rows = []
        if "candidates" not in payload:
            rows.extend(payload.get("references", []))
            rows.extend(payload.get("sources", []))
        learning = payload.get("learningContext", {})
        if isinstance(learning, dict):
            rows.extend(learning.get("documents", []))
        for row in rows:
            if isinstance(row, dict):
                for field in ("content", "excerpt"):
                    if isinstance(row.get(field), str) and not re.search(r"资格|报考条件|仅限|不得|不接受", row[field]):
                        excerpts.append((row, field))
        excerpts.sort(key=lambda item: self._relevance(query, str(item[0][item[1]])))
        for row, field in excerpts:
            if fits():
                break
            original = str(row[field])
            if len(original) <= 128:
                continue
            low, high = 128, len(original)
            while low < high:
                middle = (low + high + 1) // 2
                row[field] = original[:middle] + "\n[节选，后文未提供]"
                if fits():
                    low = middle
                else:
                    high = middle - 1
            row[field] = original[:low] + "\n[节选，后文未提供]"
            self.shortened_excerpts += 1
        statistics = learning.get("statistics", {}) if isinstance(learning, dict) else {}
        groups = statistics.get("learningProfile", {}).get("groups", [])
        groups.sort(key=lambda row: (-self._relevance(query, wire_json(row)), -float(row.get("priority") or 0)))
        for rows in (statistics.get("daily", []), groups, statistics.get("knowledgePoints", [])):
            self._trim_rows(rows, fits, latest=rows is statistics.get("daily"))
        if not fits():
            raise ModelUnavailable("context_budget_exceeded")
        return wire_json(messages)

    def _trim_rows(self, rows: list[dict[str, JsonValue]], fits: Callable[[], bool], *, latest: bool) -> None:
        """Select a bounded prefix/recent suffix without re-tokenizing per row."""
        if not rows or fits():
            return
        original = rows[:]
        rows.clear()
        if fits():
            low, high = 0, len(original)
            while low < high:
                middle = (low + high + 1) // 2
                rows[:] = original[-middle:] if latest else original[:middle]
                if fits():
                    low = middle
                else:
                    high = middle - 1
            rows[:] = (original[-low:] if latest else original[:low]) if low else []
        self.removed_statistics += len(original) - len(rows)

    @staticmethod
    def _relevance(query: str, content: str) -> int:
        terms = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2}", query.lower())
        return sum(term in content.lower() for term in set(terms))
