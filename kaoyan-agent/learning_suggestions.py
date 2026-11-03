"""Deterministic, authorized learning advice candidates for model selection."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from core.context import JsonValue, wire_json

MAX_CANDIDATES_PER_KIND = 5
DIFFICULTIES = {"EASY": "简单", "MEDIUM": "中等", "HARD": "困难"}
SuggestionAction = Literal["REVIEW_CONCEPT", "REVIEW_ATTEMPT", "COLLECT_SAMPLES", "PRACTICE_RELATED"]


@dataclass(frozen=True)
class SuggestionCandidate:
    """One immutable suggestion with code-authored text and exact provenance."""

    action: SuggestionAction
    text: str
    evidence_refs: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()

    @property
    def candidate_id(self) -> str:
        """Keep identifiers stable when unrelated context rows are removed."""
        value = [self.action, self.text, list(self.evidence_refs), list(self.source_ids)]
        return "advice_" + sha256(wire_json(value).encode()).hexdigest()[:24]

    def model_data(self) -> dict[str, JsonValue]:
        """Expose bounded data, never additional model instructions."""
        return {
            "candidateId": self.candidate_id,
            "action": self.action,
            "text": self.text,
            "evidenceRefs": list(self.evidence_refs),
            "sourceIds": list(self.source_ids),
        }


def rows(value: JsonValue) -> list[dict[str, JsonValue]]:
    """Read structured rows without treating prose as evidence."""
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def count(row: dict[str, JsonValue], *keys: str) -> int | None:
    """Accept explicit nonnegative integer counts, excluding booleans."""
    for key in keys:
        value = row.get(key)
        if type(value) is int and value >= 0:
            return value
    return None


def graded_attempt(row: dict[str, JsonValue]) -> bool:
    """Require an actual submitted snapshot before offering review of its answer."""
    return (
        row.get("answered") is True
        and not row.get("snapshotMissing")
        and row.get("snapshotStatus") not in {"MISSING", "WITHDRAWN", "INVALID"}
        and (count(row, "version") or 0) > 0
        and row.get("answer") in {"A", "B", "C", "D"}
    )


def suggestion_candidates(
    context: dict[str, JsonValue], sources: dict[str, dict[str, JsonValue]],
) -> list[SuggestionCandidate]:
    """Build bounded choices using only the current authorized, visible snapshot."""
    candidates: list[SuggestionCandidate] = []
    evidence = {str(row["ref"]): row for row in rows(context.get("evidence")) if "ref" in row}
    stats_value = context.get("statistics")
    stats = stats_value if isinstance(stats_value, dict) else {}
    stats_refs = tuple(
        ref for ref, row in evidence.items() if row.get("kind") in {"stats", "statistics"}
    )[:1]
    total = count(stats, "questionCount")
    if total is not None and total < 5:
        candidates.append(SuggestionCandidate(
            "COLLECT_SAMPLES",
            "本轮区间统计样本不足5次，建议补充独立练习后再判断掌握情况；两类样本口径分别保留。",
            stats_refs,
        ))
    points = [
        row for row in rows(stats.get("knowledgePoints"))
        if isinstance(row.get("knowledgePoint") or row.get("name"), str)
        and (row.get("knowledgePoint") or row.get("name"))
        and count(row, "questionCount", "count") is not None
        and count(row, "questionCount", "count") < 5
    ]
    for row in points[:MAX_CANDIDATES_PER_KIND]:
        topic = str(row.get("knowledgePoint") or row.get("name"))[:120]
        samples = count(row, "questionCount", "count")
        candidates.append(SuggestionCandidate(
            "COLLECT_SAMPLES",
            f"{topic}：本轮区间有效作答{samples}次，样本不足5次；建议补充该知识点的练习，暂不判断掌握程度。",
            stats_refs,
        ))
    profile = stats.get("learningProfile")
    groups = rows(profile.get("groups")) if isinstance(profile, dict) else []
    small_groups = [
        row for row in groups
        if isinstance(row.get("knowledgePoint"), str) and row.get("knowledgePoint")
        and isinstance(row.get("subject"), str) and row.get("subject")
        and row.get("difficulty") in DIFFICULTIES
        and count(row, "samples") is not None and count(row, "samples") < 5
    ]
    for row in small_groups[:MAX_CANDIDATES_PER_KIND]:
        topic = str(row["knowledgePoint"])[:120]
        subject = str(row["subject"])[:120]
        difficulty = DIFFICULTIES[str(row["difficulty"])]
        candidates.append(SuggestionCandidate(
            "COLLECT_SAMPLES",
            f"{subject}·{topic}（{difficulty}）：规则画像独立样本{row['samples']}条，不足5条；"
            "建议补充该分组的独立作答，不与区间有效作答次数混用。",
            stats_refs,
        ))
    for source_id, source in list(sources.items())[:MAX_CANDIDATES_PER_KIND]:
        topic = str(source.get("title") or "所引概念")[:120]
        candidates.append(SuggestionCandidate(
            "REVIEW_CONCEPT", f"建议复习{topic}的审核资料，核对定义与适用条件。",
            source_ids=(source_id,),
        ))
    attempts = [
        row for row in rows(context.get("items"))
        if str(row.get("ref")) in evidence and graded_attempt(row)
    ]
    for row in attempts[:MAX_CANDIDATES_PER_KIND]:
        ref = str(row["ref"])
        candidates.append(SuggestionCandidate(
            "REVIEW_ATTEMPT", f"建议回顾[{ref}]的已保存作答及该版本解析，核对可能错因。", (ref,),
        ))
    if total or attempts or sources:
        refs = (str(attempts[0]["ref"]),) if attempts else stats_refs if total else ()
        source_ids = (next(iter(sources)),) if not refs and not total and sources else ()
        candidates.append(SuggestionCandidate(
            "PRACTICE_RELATED", "建议围绕本轮学习内容选择审核练习；请通过练习入口预览并确认后开始。",
            refs, source_ids,
        ))
    return list({candidate.candidate_id: candidate for candidate in candidates}.values())


def project_suggestion_candidates(payload: dict[str, JsonValue]) -> None:
    """Refresh candidates after every context reduction; never modify raw records."""
    value = payload.get("learningContext")
    context = value if isinstance(value, dict) else {}
    sources = {str(row["id"]): row for row in rows(payload.get("references")) if "id" in row}
    payload["suggestionCandidates"] = [candidate.model_data() for candidate in suggestion_candidates(context, sources)]
