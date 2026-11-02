"""Scenario-specific example requests appended to clarifications.

Every example is itself a request the local rules route to the intended scenario,
so copying it never lands in another generic clarification.
"""

import re

from agents.planning import ADMISSION_EXAMPLE, ADMISSION_SPLIT, explicit_schools
from schemas import ConversationResolution


EXAMPLE_MARK = "\n推荐问法："
MESSAGE_LIMIT = 750
GENERIC_CLARIFICATION = "请明确你想咨询的知识、择校条件，或要创建和修改的文档。"
KNOWLEDGE_EXAMPLE = "请解释 TCP 拥塞控制的过程，并举例说明。"
NOTE_EXAMPLE = "请创建一份关于 TCP 拥塞控制的复习笔记。修改已有笔记时请先在笔记页选择该笔记。"
LOOKUP_SCHOOL = "南京审计大学"
# Polite filler around a lone school name; anything else means the user said more.
SCHOOL_FILLER = re.compile(r"[\s，。！？、,.!?：:]|请问|我想|想要|了解|一下|看看|查查|这所|学校|怎么样|如何|情况|简介|介绍|的|呢|吧|啊|呀")
DANGLING = re.compile(r"^(?:它|这个|那个|这道|那道|上面|刚才|这|那)")


def bare_school(text: str) -> tuple[str, bool] | None:
    """Return (school, registered) when the input names one school and nothing else."""
    schools = explicit_schools(text)
    if len(schools) != 1:
        return None
    name, source = schools[0]
    rest = SCHOOL_FILLER.sub("", text.replace(name, ""))
    return (name, source is not None) if not rest else None


def bare_school_message(school: str) -> str:
    """Ask what to do with a school instead of listing unrelated capabilities."""
    return f"已识别院校“{school}”，请说明想查询库内招生信息、招生官网，还是按条件推荐院校。"


def _schools(text: str) -> list[tuple[str, bool]]:
    """Explicit schools in the order the user wrote them, with their registry state."""
    found = [(name, source is not None) for name, source in explicit_schools(text)]
    return sorted(found, key=lambda item: text.find(item[0]))


def _admission_example(text: str) -> str:
    schools = _schools(text)
    if len(schools) > 1:
        return f"查官网{schools[0][0]}。其他院校请分开发送。"
    if schools and not schools[0][1]:
        return f"查询{schools[0][0]}招生信息（查看院校库资料）；或选择登记院校，例如：{ADMISSION_EXAMPLE}"
    return ADMISSION_EXAMPLE


def _lookup_example(text: str) -> str:
    schools = _schools(text)
    if len(schools) > 1:
        return f"查询{schools[0][0]}招生信息。{schools[1][0]}请另行发送。"
    name = schools[0][0] if schools else LOOKUP_SCHOOL
    return f"查询{name}招生信息；需要筛选时只写一个年份和一个专业代码，如：查询{name}2027年085404招生信息。"


def _requested_operation(plan: ConversationResolution) -> str:
    """Clarified plans drop the operation; recover the asked one from the text for the example only."""
    if plan.operation != "NONE":
        return plan.operation
    text = plan.standaloneQuery or ""
    for pattern, operation in (
        (r"(?:取消|移出|移除|删除).{0,12}收藏|收藏.{0,12}(?:取消|移出|移除|删除)", "FAVORITE_REMOVE"),
        (r"(?:移出|删除|移除|取消).{0,12}错题|错题.{0,12}(?:移出|删除|移除|取消)", "WRONG_REMOVE"),
        (r"收藏", "FAVORITE_ADD"),
        (r"练习|刷题|组题|出题|做几道", "PRACTICE_CREATE"),
    ):
        if re.search(pattern, text):
            return operation
    return "NONE"


def _learning_example(plan: ConversationResolution) -> str:
    operation = _requested_operation(plan)
    if operation == "PRACTICE_CREATE":
        return "做几道TCP题；或用我的收藏安排10道题练习。"
    if operation == "FAVORITE_REMOVE":
        return "取消收藏错题本中涉及 TCP 的题目；若指上次回答，可说：取消收藏 Q1。"
    if operation == "WRONG_REMOVE":
        return "把错题本中涉及 TCP 的题目移出错题；若指上次回答，可说：把 Q1 移出错题。"
    if operation == "FAVORITE_ADD":
        return "将我的错题本中涉及 TCP 的题目加入收藏；若指上次回答，可说：收藏 Q1 和 Q2。"
    return "请分析我的错题本中涉及 TCP 的题目。"


def _chat_example(message: str, text: str) -> str:
    school = bare_school(text)
    if school is not None:
        name, registered = school
        return f"查询{name}招生信息" + (f"；查官网{name}" if registered else "") + "。"
    if DANGLING.search(text.strip()):
        return "请把指代换成具体内容，例如：TCP 拥塞控制中的慢开始是什么意思？"
    if "笔记" in text or "笔记" in message:
        return NOTE_EXAMPLE
    if re.search(r"练习|刷题|出题|组题", text):
        return "做几道TCP题。"
    if re.search(r"择校|院校|报考|学硕|专硕", text):
        return "推荐2027年085404专硕院校，地区优先上海。"
    return KNOWLEDGE_EXAMPLE


def example_for(message: str, plan: ConversationResolution) -> str:
    """Pick one routable example that matches the clarification scenario."""
    text = plan.standaloneQuery or ""
    if plan.action == "ADMISSION_LINKS":
        return _admission_example(text)
    if plan.action == "SCHOOL_LOOKUP":
        return _lookup_example(text)
    if plan.action == "SCHOOL_RECOMMEND":
        return "推荐2027年085404专硕院校，地区优先上海。"
    if plan.action.startswith("DOCUMENT_"):
        if "选择" in message:
            return "在笔记页选中要修改的笔记后发送：在这份笔记中补充 TCP 拥塞控制的例子。"
        return NOTE_EXAMPLE
    if plan.action == "LEARNING_ANALYSIS":
        return _learning_example(plan)
    return _chat_example(message, text)


def clarification_with_example(message: str, plan: ConversationResolution) -> str:
    """Append one scenario example unless the message already carries its own."""
    if "推荐问法" in message or message == ADMISSION_SPLIT:
        return message
    return message[:MESSAGE_LIMIT] + EXAMPLE_MARK + example_for(message, plan)
