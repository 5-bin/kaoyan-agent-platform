"""Deterministic claim/citation support checks.

The model chooses source ids; this module checks whether the cited excerpts
actually share enough vocabulary with the claim. It is deliberately a lexical
baseline, not a semantic entailment model: it catches unsupported additions
(e.g. "三次握手" when the excerpt only describes sequence/ack/retransmission)
but cannot prove logical entailment or detect every contradiction.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

MIN_RATIO = 0.34
SUPPORTED_RATIO = 0.8
PARTIAL_RATIO = 0.5

_SKIP = re.compile(r"^(以下|参考|注[:：]|来源[:：]|依据[:：])"
                   r"|(资料(未|没有)|未提供|无法|不作补充|不做补充|不能据此)")
_SENTENCE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_SCOPE_NOTE = re.compile(r"资料未(?:进一步)?(?:说明|覆盖)(?:该细节|该问题)[。.]?")


def tokens(text: str) -> set[str]:
    """ASCII words plus Chinese bigrams; single Chinese characters are too weak."""
    lowered = text.lower()
    words = re.findall(r"[a-z0-9]{2,}", lowered)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", lowered))
    bigrams = [chinese[index:index + 2] for index in range(len(chinese) - 1)]
    return set(words + bigrams)


def sentences(text: str) -> list[str]:
    return [value.strip() for value in _SENTENCE.findall(text or "") if value.strip()]


def units(text: str, *, strict: bool = False) -> list[str]:
    """Merge short fragments so terse claims (e.g. "端口号为99。") cannot skip checks."""
    merged: list[str] = []
    pending = ""
    for sentence in sentences(text):
        if (_SCOPE_NOTE.fullmatch(sentence) if strict else _SKIP.match(sentence)):
            continue
        pending += sentence
        if len(pending) >= 10:
            merged.append(pending)
            pending = ""
    if pending and merged:
        merged[-1] += pending
    elif pending:
        merged.append(pending)
    return merged


def _numbers(text: str) -> list[Decimal]:
    """Whole Arabic numbers; "01" and "1.0" compare equal to "1"."""
    return [Decimal(value) for value in _NUMBER.findall(text or "")]


def trusted_numbers(facts: str) -> set[Decimal]:
    """Numbers in the trusted facts plus the percentages of their ratios.

    Business services send rates as ratios (0.2787); a rounded percentage with
    at most two decimals ("28%", "27.9%", "27.87%") is a presentation of the
    same fact, not a recomputation.
    """
    values = set()
    for value in _numbers(facts):
        values.add(value)
        if 0 <= value <= 1 and value.as_tuple().exponent < 0:
            percent = value * 100
            for places in range(3):
                values.add(percent.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))
    return values


def numbers_supported(text: str, facts: str) -> bool:
    """Every Arabic number in model prose must be a whole number of the trusted facts.

    Model prose may not recompute or invent counts, rates or scores; "1" is not
    supported merely because the facts contain "61". Chinese numerals, wording
    such as "全部答对" and whether a number refers to the right topic or counting
    scope are not detected by this baseline.
    """
    allowed = trusted_numbers(facts)
    return all(value in allowed for value in _numbers(text))


def _excerpts(docs: Iterable) -> tuple[str, set[str]]:
    contents = []
    for doc in docs:
        content = doc.get("content") if isinstance(doc, dict) else getattr(doc, "content", "")
        if content:
            contents.append(content)
    joined = "\n".join(contents)
    return joined, tokens(joined)


def score_claim(claim: str, docs: Iterable) -> tuple[float, str | None]:
    """Return (overlap ratio, failure reason). Numbers must appear in the excerpts."""
    claim_tokens = tokens(claim)
    if not claim_tokens:
        return 0.0, "empty_claim"
    excerpt_text, excerpt_tokens = _excerpts(docs)
    if not excerpt_tokens:
        return 0.0, "missing_excerpt"
    overlap = claim_tokens & excerpt_tokens
    ratio = len(overlap) / len(claim_tokens)
    if not set(_numbers(claim)) <= set(_numbers(excerpt_text)):
        return min(ratio, 0.2), "number_mismatch"
    if not overlap:
        return 0.0, "no_overlap"
    if ratio < MIN_RATIO:
        return ratio, "low_overlap"
    return ratio, None


def _coverage_text(text: str, source_ids: list[str]) -> str:
    """Normalize presentation only; retain factual characters, numbers and negation."""
    text = unicodedata.normalize("NFKC", text)
    for source_id in source_ids:
        text = text.replace("[" + unicodedata.normalize("NFKC", source_id) + "]", "")
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-+*]\s+|\d+[.)、]\s+)", "", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", "", text)


def fully_supported(report: Mapping[str, object]) -> bool:
    """Require every checked unit, rather than the legacy aggregate ratio threshold."""
    return bool(report.get("checked")) and report.get("checked") == report.get("supported")


def verify(
    answer: str,
    source_ids: list[str],
    docs,
    claims: list[dict] | None = None,
    *,
    min_ratio: float = MIN_RATIO,
    strict: bool = False,
) -> dict:
    """Verify one model answer.

    ``docs`` may be a list of Document/objects with ``id``/``content`` or a dict
    id -> document. When the model supplied per-claim source ids, each claim is
    checked against only its own cited excerpts; otherwise every sentence is
    checked against the union of the answer's cited excerpts.
    """
    by_id = docs if isinstance(docs, dict) else {
        (doc.get("id") if isinstance(doc, dict) else getattr(doc, "id", "")): doc for doc in docs
    }
    checked = 0
    supported = 0
    unsupported: list[dict] = []
    items: list[dict] = []

    def check(text: str, ids: list[str]) -> None:
        nonlocal checked, supported
        text = (text or "").strip()
        if not text or (not strict and not claims and (len(text) < 10 or _SKIP.match(text))):
            return
        scoring_text = _coverage_text(text, list(by_id)) if strict or claims else text
        if not scoring_text:
            return
        cited = [by_id[value] for value in ids if value in by_id]
        unknown = [value for value in ids if value not in by_id]
        checked += 1
        item = {"text": text[:240], "sourceIds": list(ids)[:5], "supported": False}
        if unknown or not cited:
            item["reason"] = "unknown_source"
            items.append(item)
            unsupported.append(item)
            return
        ratio, reason = score_claim(scoring_text, cited)
        item["ratio"] = round(ratio, 3)
        if reason is None and ratio >= min_ratio:
            supported += 1
            item["supported"] = True
        else:
            item["reason"] = reason or "low_overlap"
            unsupported.append(item)
        items.append(item)

    if claims:
        for claim in claims:
            check(str(claim.get("text", "")), list(claim.get("sourceIds", [])))
        normalized_answer = _coverage_text("".join(units(answer, strict=True)), list(by_id))
        normalized_claims = _coverage_text("".join(str(claim.get("text", "")) for claim in claims), list(by_id))
        if normalized_answer != normalized_claims:
            checked += 1
            item = {"text": "正文与逐条结论未按顺序完整对应。", "sourceIds": [],
                    "supported": False, "reason": "low_overlap"}
            unsupported.append(item)
            items.append(item)
    else:
        for unit in units(answer, strict=strict):
            check(unit, list(source_ids))

    ratio = round(supported / checked, 3) if checked else 0.0
    if not checked:
        status = "NOT_CHECKED"
    elif strict and supported != checked:
        status = "PARTIAL" if supported else "UNSUPPORTED"
    elif ratio >= SUPPORTED_RATIO:
        status = "SUPPORTED"
    elif ratio >= PARTIAL_RATIO:
        status = "PARTIAL"
    else:
        status = "UNSUPPORTED"
    return {"status": status, "checked": checked, "supported": supported,
            "ratio": ratio, "unsupported": unsupported[:10], "items": items[:20]}


def aggregate(items: list[dict]) -> dict:
    """Merge per-candidate/per-claim reports into one displayable summary."""
    checked = sum(item.get("checked", 0) for item in items)
    supported = sum(item.get("supported", 0) for item in items)
    ratio = round(supported / checked, 3) if checked else 0.0
    if not checked:
        status = "NOT_CHECKED"
    elif ratio >= SUPPORTED_RATIO:
        status = "SUPPORTED"
    elif ratio >= PARTIAL_RATIO:
        status = "PARTIAL"
    else:
        status = "UNSUPPORTED"
    unsupported = [entry for item in items for entry in item.get("unsupported", [])][:10]
    claim_items = [entry for item in items for entry in item.get("items", [])][:20]
    return {"status": status, "checked": checked, "supported": supported,
            "ratio": ratio, "unsupported": unsupported, "items": claim_items}
