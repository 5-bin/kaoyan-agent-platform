"""Local partial JSON projection; final results still require strict validation."""

import json


def project(value: object) -> dict[str, str]:
    """Expose only the same four presentation slots, never reasoning or tools."""
    if not isinstance(value, dict):
        return {}
    result = {
        key: value[key]
        for key in ("answer", "content", "summary")
        if isinstance(value.get(key), str)
    }
    if isinstance(value.get("explanation"), str):
        result["answer"] = value["explanation"]
    for index, item in enumerate(value.get("explanations", [])):
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            result[f"candidate.{index}"] = item["text"]
    return result


def partial_json(text: str) -> object:
    """Close incomplete containers/strings for presentation, never for saving."""
    closing: list[str] = []
    quoted = False
    escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            closing.append("]" if char == "[" else "}")
        elif char in "]}":
            if not closing or closing.pop() != char:
                return None
    prefix = text[:-1] if quoted and escaped else text
    suffix = ('"' if quoted else "") + "".join(reversed(closing))
    while prefix:
        try:
            return json.loads(prefix + suffix)
        except (ValueError, TypeError):
            prefix = prefix[:-1]
    return None


def parse_result(content: str) -> dict:
    """Validate the complete JSON object; partial repairs never become results."""
    content = content.strip()
    if content.startswith("```") and content.endswith("```"):
        content = content[3:-3].removeprefix("json").strip()
    value = json.loads(content)
    if not isinstance(value, dict) or not value:
        raise ValueError("模型结果必须是非空JSON对象")
    json.dumps(value, ensure_ascii=False).encode("utf-8")
    return value
