"""2026-11-03: school comparison reads the degree type from the profile before asking."""

import pytest
from pydantic import ValidationError

from agents.school import DEGREE_FOLLOW_UP
from schemas import Profile
from tests.test_workflows import client, post, request


def school(profile: dict, preferences: dict) -> dict:
    """Run one rule-only school recommendation and return its public result."""
    with client() as c:
        body = request(profile=profile, preferences={**preferences, "explainWithAi": False})
        return post(c, body)["result"]


def test_profile_degree_type_completes_without_follow_up():
    result = school({"examYear": 2027, "targetMajor": "081200", "degreeType": "academic"}, {})
    assert result["outcome"] == "COMPLETED"
    assert result["answer"].startswith("学位类型：学硕（来自个人档案")
    assert result["preferences"]["degreeType"] == "academic"
    assert {c["degreeType"] for c in result["candidates"]} == {"academic"}
    assert result["profileSnapshot"]["degreeType"] == "academic"


def test_turn_degree_type_overrides_profile():
    result = school({"examYear": 2027, "targetMajor": "085404", "degreeType": "academic"},
                    {"degreeType": "professional"})
    assert result["outcome"] == "COMPLETED"
    assert not result["answer"].startswith("学位类型：")
    assert {c["degreeType"] for c in result["candidates"]} == {"professional"}


def test_single_catalog_degree_is_inferred_from_major_code():
    result = school({"examYear": 2027, "targetMajor": "085404"}, {})
    assert result["outcome"] == "COMPLETED"
    assert result["answer"].startswith("学位类型：专硕（按目标专业代码在院校库中推断")
    assert {c["degreeType"] for c in result["candidates"]} == {"professional"}


def test_ambiguous_majors_still_ask_to_fill_the_profile():
    result = school({"examYear": 2027}, {"majorCodes": ["081200", "085404"]})
    assert result["outcome"] == "NEEDS_INPUT"
    assert result["followUp"] == [DEGREE_FOLLOW_UP]


def test_profile_rejects_unknown_degree_type():
    assert Profile(degreeType="professional").degreeType == "professional"
    with pytest.raises(ValidationError):
        Profile(degreeType="doctor")


@pytest.mark.asyncio
async def test_compound_chat_uses_profile_degree_without_asking():
    """The reported composite request completes school comparison from the profile."""
    from schemas import ConversationRequest
    from tests.test_conversation import workflow

    flow = workflow()
    req = ConversationRequest(
        taskId="conversation-test", userId=1, taskType="CHAT",
        userInput="分析我的薄弱点，安排下周复习并比较院校",
        profile={"examYear": 2027, "targetMajor": "081200", "degreeType": "academic"},
        conditions={"examYear": 2027, "majorCodes": ["081200"]},
        learningContext={"statistics": {"questionCount": 3, "correctCount": 1,
                                        "knowledgePoints": [{"knowledgePoint": "线程", "questionCount": 3}]}},
    )
    req.preparedPlan = await flow.plan(req)
    result = await flow.run(req)
    assert [s["outcome"] for s in result["sections"]][-1] == "COMPLETED"
    assert DEGREE_FOLLOW_UP not in result.get("followUp", [])
    assert "学位类型：学硕（来自个人档案" in result["answer"]
    assert result["candidates"] and {c["degreeType"] for c in result["candidates"]} == {"academic"}
    flow.engine.model.generate.assert_not_awaited()
