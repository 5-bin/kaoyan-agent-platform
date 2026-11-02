"""Bounded structured-result helper shared by read-only MCP tools."""

import json

MAX_RESULT_BYTES = 64 * 1024


def checked_size(value: object) -> None:
    """Reject oversized structured evidence without truncating required fields."""
    if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > MAX_RESULT_BYTES:
        raise ValueError("MCP_RESULT_TOO_LARGE")
