"""Conservative, request-scoped choices for recoverable ambiguities."""

from agents.guidance import bare_school
from schemas import ConversationResolution


def clarification_options(result: dict, plan: ConversationResolution) -> list[dict[str, str]]:
    """Return only choices grounded in the current clarification and query."""
    needs_input = result.get("outcome") == "NEEDS_INPUT" or any(
        section.get("outcome") == "NEEDS_INPUT" for section in result.get("sections", [])
    )
    query = plan.standaloneQuery.strip()
    if not needs_input or not query or len(query) > 1800:
        return []
    message = plan.clarification or result.get("answer", "")
    if "笔记要整理知识讲解、练习题目还是已完成作答" in message:
        return [
            {"label": label, "reply": query + "；笔记要整理" + label}
            for label in ("知识讲解", "练习题目", "已完成作答")
        ]
    if (
        "请选择学硕或专硕" in result.get("followUp", [])
        and "学硕" not in query and "专硕" not in query
    ):
        return [
            {"label": label, "reply": query + "；报考" + label}
            for label in ("学硕", "专硕")
        ]
    school = bare_school(query) if plan.action == "CHAT" and not plan.clarification else None
    if school is not None and "已识别院校" in message:
        name, registered = school
        return [
            {"label": label, "reply": reply}
            for label, reply in (
                ("库内招生信息", f"查询{name}招生信息"),
                *((("招生官网", f"查官网{name}"),) if registered else ()),
                ("按条件推荐", "推荐院校"),
            )
        ]
    if (plan.action == "CHAT" and not plan.clarification
            and "请明确你想咨询的知识、择校条件" in message):
        return [
            {"label": label, "reply": query + "；" + reply}
            for label, reply in (
                ("知识辅导", "我想咨询408知识"),
                ("分析学情", "我想分析我的学习情况"),
                ("院校推荐", "我想咨询院校推荐"),
            )
        ]
    return []
