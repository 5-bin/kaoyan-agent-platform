"""Deterministic claim/citation support checks.

The model chooses source ids; this module checks whether the cited excerpts
actually share enough vocabulary with the claim. It is deliberately a lexical
baseline, not a semantic entailment model: it catches unsupported additions
(e.g. "三次握手" when the excerpt only describes sequence/ack/retransmission)
but cannot prove logical entailment or detect every contradiction.
"""
from __future__ import annotations

import re
from typing import Iterable

MIN_RATIO = 0.34
SUPPORTED_RATIO = 0.8
PARTIAL_RATIO = 0.5

_SKIP = re.compile(r"^(以下|参考|注[:：]|来源[:：]|依据[:：])"
                   r"|(资料(未|没有)|未提供|无法|不作补充|不做补充|不能据此)")
_SENTENCE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")


def tokens(text: str) -> set[str]:
    """ASCII words plus Chinese bigrams; single Chinese characters are too weak."""
    lowered = text.lower()
    words = re.findall(r"[a-z0-9]{2,}", lowered)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", lowered))
    bigrams = [chinese[index:index + 2] for index in range(len(chinese) - 1)]
    return set(words + bigrams)


def sentences(text: str) -> list[str]:
    return [value.strip() for value in _SENTENCE.findall(text or "") if value.strip()]


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
    numbers = re.findall(r"\d+", claim)
    if numbers:
        missing = [value for value in numbers if value not in excerpt_text]
        if missing:
            return min(ratio, 0.2), "number_mismatch"
    if not overlap:
        return 0.0, "no_overlap"
    if ratio < MIN_RATIO:
        return ratio, "low_overlap"
    return ratio, None


def verify(
    answer: str,
    source_ids: list[str],
    docs,
    claims: list[dict] | None = None,
    *,
    min_ratio: float = MIN_RATIO,
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
        if len(text) < 10 or _SKIP.match(text):
            return
        if not ids:
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
        ratio, reason = score_claim(text, cited)
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
    else:
        for sentence in sentences(answer):
            check(sentence, list(source_ids))

    ratio = round(supported / checked, 3) if checked else 0.0
    if not checked:
        status = "NOT_CHECKED"
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
