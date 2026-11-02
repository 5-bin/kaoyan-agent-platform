"""2026-11-02 scenario-specific clarification examples and their routing."""

import pytest

from agents.guidance import EXAMPLE_MARK, bare_school
from tests.test_conversation import workflow
from tests.test_review_fixes import request


async def answer(text: str) -> dict:
    """Plan locally and run the request without any model."""
    flow = workflow()
    plan = await flow.plan(request(text))
    return await flow.run(request(text, preparedPlan=plan.model_dump(by_alias=True)))


def example(result: dict) -> str:
    """The single example appended after the clarification."""
    return result["answer"].split(EXAMPLE_MARK, 1)[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("text,expected", [
    ("燕山大学", "查询燕山大学招生信息；查官网燕山大学。"),
    ("查官网", "查官网南京审计大学。"),
    ("查官网某某理工大学", "查询某某理工大学招生信息（查看院校库资料）"),
    ("查官网清华大学和北京大学", "查官网清华大学。其他院校请分开发送。"),
    ("招生信息", "查询南京审计大学招生信息"),
    ("帮我查清华大学和北京大学的招生信息", "查询清华大学招生信息。北京大学请另行发送。"),
    ("查询清华大学2026年和2027年招生信息", "查询清华大学2027年085404招生信息"),
    ("帮我整理笔记", "复习笔记"),
    ("它是什么意思", "请把指代换成具体内容"),
    ("推荐院校", "推荐2027年085404专硕院校"),
])
async def test_example_matches_the_scenario(text, expected):
    result = await answer(text)
    assert result["outcome"] == "NEEDS_INPUT"
    assert expected in example(result)
    assert "TCP 拥塞控制的过程" not in example(result)


@pytest.mark.asyncio
async def test_unclear_knowledge_request_keeps_the_knowledge_example():
    assert example(await answer("嗯")) == "请解释 TCP 拥塞控制的过程，并举例说明。"


@pytest.mark.asyncio
async def test_split_clarification_carries_its_own_example_only():
    result = await answer("查询北京大学招生信息并制定复习计划")
    assert EXAMPLE_MARK not in result["answer"] and "查询北京大学招生信息" in result["answer"]


@pytest.mark.asyncio
async def test_bare_school_asks_what_to_do_with_school_options():
    result = await answer("燕山大学怎么样")
    assert result["answer"].startswith("已识别院校“燕山大学”")
    options = {item["label"]: item["reply"] for item in result["clarificationOptions"]}
    assert options == {"库内招生信息": "查询燕山大学招生信息", "招生官网": "查官网燕山大学", "按条件推荐": "推荐院校"}


@pytest.mark.asyncio
async def test_unregistered_bare_school_offers_no_link_option():
    result = await answer("某某理工大学")
    assert [item["label"] for item in result["clarificationOptions"]] == ["库内招生信息", "按条件推荐"]


def test_bare_school_requires_only_filler():
    assert bare_school("请问燕山大学") == ("燕山大学", True)
    assert bare_school("燕山大学的计算机怎么考") is None
    assert bare_school("燕山大学和北京大学") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("text,action,operation", [
    ("查询燕山大学招生信息", "SCHOOL_LOOKUP", "NONE"),
    ("查官网燕山大学", "ADMISSION_LINKS", "NONE"),
    ("查询南京审计大学2027年085404招生信息", "SCHOOL_LOOKUP", "NONE"),
    ("做几道TCP题", "LEARNING_ANALYSIS", "PRACTICE_CREATE"),
    ("用我的收藏安排10道题练习", "LEARNING_ANALYSIS", "PRACTICE_CREATE"),
    ("推荐2027年085404专硕院校，地区优先上海", "SCHOOL_RECOMMEND", "NONE"),
    ("请分析我的错题本中涉及 TCP 的题目", "LEARNING_ANALYSIS", "NONE"),
    ("将我的错题本中涉及 TCP 的题目加入收藏", "LEARNING_ANALYSIS", "FAVORITE_ADD"),
    ("取消收藏错题本中涉及 TCP 的题目", "LEARNING_ANALYSIS", "FAVORITE_REMOVE"),
    ("把错题本中涉及 TCP 的题目移出错题", "LEARNING_ANALYSIS", "WRONG_REMOVE"),
    ("请创建一份关于 TCP 拥塞控制的复习笔记", "DOCUMENT_CREATE", "NONE"),
    ("TCP 拥塞控制中的慢开始是什么意思？", "KNOWLEDGE_QA", "NONE"),
])
async def test_every_suggested_example_routes_to_its_scenario(text, action, operation):
    plan = await workflow().plan(request(text))
    assert (plan.action, plan.operation, plan.clarification) == (action, operation, None)
