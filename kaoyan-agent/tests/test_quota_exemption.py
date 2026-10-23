import pytest
from types import SimpleNamespace
from llm_client import ModelClient, quota_exempt

@pytest.mark.asyncio
async def test_exemption_preserves_other_users_daily_budget():
    client = ModelClient(SimpleNamespace(LLM_ENABLED=True, MAX_MODEL_CALLS_PER_DAY=1))
    client.budget.consume(1)
    token = quota_exempt.set(True)
    try:
        # Missing provider config stops before network, after the budget check.
        with pytest.raises(AttributeError, match="LLM_API_KEY"):
            await client._generate("test", {}, object)
        assert client.budget.calls == 1
    finally:
        quota_exempt.reset(token)
    with pytest.raises(RuntimeError, match="model_limit"):
        await client._generate("test", {}, object)
