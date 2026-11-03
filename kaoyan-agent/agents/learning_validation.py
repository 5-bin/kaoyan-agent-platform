"""Validate public explanations and render suggestions without model-authored facts."""

import json
import re
from dataclasses import dataclass
from typing import cast

from core.context import JsonValue, PreparedModelInput
from core.errors import InvalidModelOutput
from grounding import aggregate, fully_supported, numbers_supported, verify
from learning import LearningAnswer, LearningSuggestion
from learning_suggestions import (
    SuggestionCandidate,
    count as _count,
    graded_attempt,
    rows as _rows,
    suggestion_candidates,
)

PERSONAL_FACT = re.compile(
    r"正确率|有效作答|答对|答错|参考分|掌握指数|独立(?:证据|样本)|"
    r"你(?:已|的|有)|样本不足|(?:共|累计)(?:完成|练习|作答)|"
    r"(?:作答|练习)[零一二两三四五六七八九十百千\d]"
)


@dataclass(frozen=True)
class LearningEnrichment:
    """Checked additions and provenance, without replacing deterministic facts."""

    lines: tuple[str, ...]
    source_ids: frozenset[str]
    evidence_refs: frozenset[str]
    citation_support: dict[str, JsonValue]


def _numeric_facts(context: dict[str, JsonValue]) -> list[int | float]:
    """Project typed count/rate values for rejection of legacy numeric prose."""
    keys = {"questionCount", "correctCount", "uniqueQuestions", "wrongCount", "wrongAttempts", "accuracy",
            "count", "correct", "samples", "referenceScore", "independentSamples", "assistedSamples", "unknownSamples"}
    values: list[int | float] = []

    def collect(value: JsonValue) -> None:
        """Inspect structured values without parsing any free-text field."""
        if isinstance(value, dict):
            for key, child in value.items():
                if key in keys and type(child) in (int, float):
                    values.append(child)
                elif isinstance(child, (dict, list)):
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(context.get("statistics"))
    for key in ("total", "readCount"):
        value = context.get(key)
        if type(value) is int:
            values.append(value)
    return values


def _legacy_suggestion(
    suggestion: LearningSuggestion, context: dict[str, JsonValue],
    sources: dict[str, dict[str, JsonValue]], evidence: dict[str, dict[str, JsonValue]],
) -> str:
    """Validate the requested suggestion against visible records and author its text."""
    if suggestion.action is None:
        raise InvalidModelOutput("suggestion_action_required")
    if not set(suggestion.sourceIds) <= sources.keys() or not set(suggestion.evidenceRefs) <= evidence.keys():
        raise InvalidModelOutput("unknown_evidence")
    items = {str(row["ref"]): row for row in _rows(context.get("items")) if "ref" in row}
    stats_value = context.get("statistics")
    stats = stats_value if isinstance(stats_value, dict) else {}
    selected = [items[ref] for ref in suggestion.evidenceRefs if ref in items]
    labels = [str(row.get("knowledgePoint") or row.get("subject") or "所选题目")[:120] for row in selected]
    labels += [str(sources[ref].get("title") or "所引概念")[:120] for ref in suggestion.sourceIds]
    topic = "、".join(dict.fromkeys(labels[:3])) or "本轮学习内容"
    if suggestion.action == "REVIEW_CONCEPT":
        if not suggestion.sourceIds:
            raise InvalidModelOutput("suggestion_source_required")
        return f"建议复习{topic}的审核资料，核对定义与适用条件。"
    if suggestion.action == "REVIEW_ATTEMPT":
        if not selected or len(selected) != len(suggestion.evidenceRefs) or not all(graded_attempt(row) for row in selected):
            raise InvalidModelOutput("suggestion_requires_graded_evidence")
        return "建议回顾" + "、".join(f"[{ref}]" for ref in suggestion.evidenceRefs) + "的已保存作答及该版本解析，核对可能错因。"
    if suggestion.action == "COLLECT_SAMPLES":
        if suggestion.sourceIds or selected or any(
            evidence[ref].get("kind") not in {"stats", "statistics"} for ref in suggestion.evidenceRefs
        ):
            raise InvalidModelOutput("suggestion_requires_statistics_evidence")
        count = _count(stats, "questionCount")
        if count is None or count >= 5:
            raise InvalidModelOutput("suggestion_requires_small_sample_evidence")
        return "本轮区间统计样本不足5次，建议补充独立练习后再判断掌握情况；两类样本口径分别保留。"
    if not suggestion.sourceIds and not selected and not (_count(stats, "questionCount") or 0):
        raise InvalidModelOutput("suggestion_requires_learning_evidence")
    return f"建议围绕{topic}选择审核练习；请通过练习入口预览并确认后开始。"


def _suggestion(
    suggestion: LearningSuggestion, context: dict[str, JsonValue],
    sources: dict[str, dict[str, JsonValue]], evidence: dict[str, dict[str, JsonValue]],
    candidates: dict[str, SuggestionCandidate],
) -> SuggestionCandidate:
    """Resolve only a current candidate or the strictly checked legacy format."""
    if suggestion.candidateId is not None:
        if suggestion.model_fields_set & {"action", "evidenceRefs", "sourceIds"}:
            raise InvalidModelOutput("mixed_suggestion_candidate")
        if suggestion.candidateId not in candidates:
            raise InvalidModelOutput("unknown_suggestion_evidence")
        return candidates[suggestion.candidateId]
    if suggestion.action is None:
        raise InvalidModelOutput("suggestion_action_required")
    text = _legacy_suggestion(suggestion, context, sources, evidence)
    return SuggestionCandidate(
        suggestion.action, text, tuple(suggestion.evidenceRefs), tuple(suggestion.sourceIds),
    )


def validate_enrichment(answer: LearningAnswer, prepared: PreparedModelInput) -> LearningEnrichment:
    """Reject all additions if any legacy text, explanation or suggestion is invalid."""
    answer = LearningAnswer.model_validate(answer.model_dump(exclude_unset=True))
    raw_context = prepared.payload.get("learningContext")
    context = raw_context if isinstance(raw_context, dict) else {}
    sources = prepared.sources()
    evidence = {str(row["ref"]): row for row in _rows(context.get("evidence")) if "ref" in row}
    if not set(answer.evidenceRefs) <= evidence.keys() or not set(answer.sourceIds) <= sources.keys():
        raise InvalidModelOutput("unknown_evidence")
    if answer.model_fields_set & {"answer", "evidenceRefs", "sourceIds"}:
        if answer.answer and not numbers_supported(answer.answer, json.dumps(_numeric_facts(context))):
            raise InvalidModelOutput("learning_number_mismatch")
        raise InvalidModelOutput("legacy_learning_output")
    if not answer.explanations and not answer.suggestions:
        raise InvalidModelOutput("empty_learning_output")
    lines: list[str] = []
    source_ids: set[str] = set()
    evidence_refs: set[str] = set()
    reports = []
    # Rebuild from records rather than trusting a supplied menu or model text.
    offered = {row.get("candidateId") for row in _rows(prepared.payload.get("suggestionCandidates"))
               if isinstance(row.get("candidateId"), str)}
    candidates = {candidate.candidate_id: candidate for candidate in suggestion_candidates(context, sources)
                  if candidate.candidate_id in offered}
    for explanation in answer.explanations:
        if not set(explanation.sourceIds) <= sources.keys():
            raise InvalidModelOutput("unknown_source")
        if PERSONAL_FACT.search(explanation.text):
            raise InvalidModelOutput("learning_personal_fact_number_mismatch")
        report = verify(explanation.text, explanation.sourceIds, sources, strict=True)
        if not fully_supported(report):
            raise InvalidModelOutput("unsupported_learning_citation")
        reports.append(report)
        source_ids.update(explanation.sourceIds)
        lines.append("概念解释：" + explanation.text)
    for suggestion in answer.suggestions:
        candidate = _suggestion(suggestion, context, sources, evidence, candidates)
        lines.append(candidate.text)
        source_ids.update(candidate.source_ids)
        evidence_refs.update(candidate.evidence_refs)
    return LearningEnrichment(tuple(dict.fromkeys(lines)), frozenset(source_ids), frozenset(evidence_refs),
                              cast(dict[str, JsonValue], aggregate(reports)))
