"""Catalog plans are deterministic, bounded and never cause provider calls."""

import pytest

from agents.planning import ModelConversationResolution
from agents.resolver import validate_plan
from core.admission_contract import AdmissionSource, load_sources
from core.errors import InvalidModelOutput
from schemas import ConversationRequest, ConversationResolution
from tests.test_conversation import workflow


def request(text: str) -> ConversationRequest:
    """Build a synthetic request without a database or real provider."""
    return ConversationRequest(taskId="catalog-test", userId=1, taskType="CHAT", userInput=text)


@pytest.mark.asyncio
@pytest.mark.parametrize("source", list(load_sources().values()), ids=lambda source: source.code)
async def test_catalog_plan_for_all_registered_schools(source: AdmissionSource) -> None:
    """Every registered school resolves locally without requiring year or major."""
    flow = workflow(enabled=True)
    req = request(f"帮我查询{source.name}的招生信息")
    req.privacy.modelAllowed = True
    req.privacy.provider = "https://open.bigmodel.cn/api/paas/v4"
    plan = await flow.plan(req)
    assert plan.action == "SCHOOL_LOOKUP"
    assert plan.schoolLookup.schoolName == source.name
    assert not plan.reads and not plan.steps and plan.operation == "NONE"
    await flow.run(req.model_copy(update={"preparedPlan": plan}))
    flow.engine.model.generate.assert_not_called()


@pytest.mark.asyncio
async def test_explicit_filters_and_link_only_route_remain_distinct() -> None:
    """Catalog filters come only from this turn; explicit links retain the MCP route."""
    flow = workflow()
    plan = await flow.plan(request("查询北京大学2027年081200专业招生目录"))
    assert plan.schoolLookup.model_dump() == {"schoolName": "北京大学", "year": 2027, "majorCode": "081200"}
    assert (await flow.plan(request("只要北京大学招生官网链接"))).action == "ADMISSION_LINKS"
    for text in ("查询招生信息", "查询北京大学和清华大学招生信息", "查询北京大学2026年和2027年招生信息"):
        plan = await flow.plan(request(text))
        assert plan.clarification and not plan.reads and not plan.steps
    assert (await flow.plan(request("查询未登记测试大学招生信息"))).schoolLookup.schoolName == "未登记测试大学"


def test_model_and_prepared_plans_cannot_invent_catalog_queries() -> None:
    """Neither a model nor a mutated prepared plan can select another institution."""
    parsed = ModelConversationResolution.model_validate({
        "action": "SCHOOL_LOOKUP", "standaloneQuery": "解释TCP", "schoolLookup": {"schoolName": "北京大学"},
    })
    assert parsed.action == "CHAT" and parsed.clarification
    plan = ConversationResolution(action="SCHOOL_LOOKUP", standaloneQuery="查询清华大学招生信息",
                                  schoolLookup={"schoolName": "北京大学"})
    with pytest.raises(InvalidModelOutput):
        validate_plan(plan, request("查询清华大学招生信息"))
