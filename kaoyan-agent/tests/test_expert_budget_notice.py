"""2026-11-03: three expert attempts, an 8-second start threshold and truthful rule notices."""

import pytest

from core.errors import ModelUnavailable
from core.runtime import CallBudget, step_model_allowed, step_rules_reason
from core.scheduling import MIN_MODEL_SECONDS, schedule_steps
from config import Settings
from schemas import ExpertStep
from tests.test_expert_audit import CONSENT
from tests.test_multiagent import request
from tests.test_conversation import workflow


def done() -> dict:
    """Return a completed rule-only expert result."""
    return {"outcome": "COMPLETED", "answer": "ok", "explanationMode": "rules", "references": []}


@pytest.mark.asyncio
async def test_fourth_eligible_expert_is_denied_with_budget_reason():
    allowance, grants, seen = CallBudget(3), [], {}

    async def execute(step, completed):
        seen[step.agent] = step_rules_reason.get()
        if step_model_allowed.get():
            grants.append(step.agent)
            allowance.consume()
        return done()

    reasons: dict[str, str] = {}
    steps = [ExpertStep(agent=name) for name in ("LEARNING", "SCHOOL", "KNOWLEDGE", "NOTE")]
    await schedule_steps(steps, execute, lambda s: True, lambda s: False, allowance, 5, 1, 0, reasons)
    assert grants == ["LEARNING", "SCHOOL", "KNOWLEDGE"] and allowance.used == 3
    assert reasons == {"NOTE": "BUDGET"} and seen["NOTE"] == "BUDGET" and seen["LEARNING"] is None
    assert step_rules_reason.get() is None


@pytest.mark.asyncio
async def test_short_remaining_stage_runs_rules_instead_of_timing_out():
    allowance, grants = CallBudget(3), []

    async def execute(step, completed):
        if step_model_allowed.get():
            grants.append(step.agent)
        return done()

    reasons: dict[str, str] = {}
    result = await schedule_steps([ExpertStep(agent="LEARNING")], execute, lambda s: True, lambda s: False,
                                  allowance, 2, 1, MIN_MODEL_SECONDS, reasons)
    assert grants == [] and reasons == {"LEARNING": "TIME"}
    assert result["LEARNING"]["outcome"] == "COMPLETED"


def test_default_stage_timeouts_fit_the_task_limit():
    config = Settings(_env_file=None, AGENT_INTERNAL_KEY="test-only-internal-key-123456")
    assert (config.CONVERSATION_EXPERT_TIMEOUT, config.CONVERSATION_SUMMARY_TIMEOUT) == (28, 4)
    assert config.CONVERSATION_PARSE_TIMEOUT + config.CONVERSATION_EXPERT_TIMEOUT \
        + config.CONVERSATION_SUMMARY_TIMEOUT <= config.AGENT_TASK_TIMEOUT
    assert MIN_MODEL_SECONDS < config.CONVERSATION_EXPERT_TIMEOUT


def composite(privacy: dict):
    """Build the reported composite request with statistics and a complete profile."""
    return request(
        "分析我的薄弱点，安排下周复习并比较院校",
        privacy=privacy,
        profile={"examYear": 2027, "targetMajor": "081200", "degreeType": "academic"},
        conditions={"examYear": 2027, "majorCodes": ["081200"]},
        learningContext={"statistics": {"questionCount": 3, "correctCount": 1,
                                        "knowledgePoints": [{"knowledgePoint": "线程", "questionCount": 3}]}},
    )


async def notices(privacy: dict, enabled: bool = True, rules_only: bool = True) -> dict[str, str]:
    """Run the composite request and return each section's notice."""
    flow = workflow(enabled=enabled)
    flow.engine.model.generate.side_effect = ModelUnavailable("synthetic")
    req = composite(privacy)
    req.preparedPlan = await flow.plan(req)
    result = await flow.run(req)
    if rules_only:
        flow.engine.model.generate.assert_not_awaited()
    return {item["agent"]: item.get("notice", "") for item in result["sections"]}


@pytest.mark.asyncio
async def test_missing_consent_is_named_on_every_section():
    found = await notices({**CONSENT, "modelAllowed": False})
    assert set(found) == {"LEARNING", "STUDY_PLAN", "SCHOOL"}
    assert all(text.startswith("未开启外部模型授权") for text in found.values())
    assert not any("未追加模型请求" in text for text in found.values())


@pytest.mark.asyncio
async def test_missing_category_and_stale_provider_are_named():
    # Learning and the plan may use the (mocked) model; only the school step lacks "profile".
    found = await notices({**CONSENT, "scopes": ["stats"]}, rules_only=False)
    assert found["SCHOOL"].startswith("未授权外发“个人档案”")
    stale = await notices({**CONSENT, "provider": "https://api.example.com/v1"})
    assert all("授权已失效" in text for text in stale.values())


@pytest.mark.asyncio
async def test_server_switch_is_reported_before_user_consent():
    found = await notices({**CONSENT, "modelAllowed": False}, enabled=False)
    assert all(text.startswith("外部模型未在服务端启用") for text in found.values())
