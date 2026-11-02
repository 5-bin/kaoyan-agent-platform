"""Exemption skips only the daily quota, using a controlled SDK transport."""

import httpx
import pytest
from openai import AsyncOpenAI

from config import Settings
from llm_client import ModelClient, quota_exempt
from schemas import Answer


@pytest.mark.asyncio
async def test_exemption_preserves_other_users_daily_budget():
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"answer":"合成回答","sourceIds":["s"]}'}, "finish_reason": "stop"}]})
    client = ModelClient(Settings(_env_file=None, AGENT_INTERNAL_KEY="synthetic-key-12345678", LLM_ENABLED=True, LLM_API_KEY="synthetic", MAX_MODEL_CALLS_PER_DAY=1))
    client.client = AsyncOpenAI(api_key="synthetic", max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    client.budget.consume(1)
    token = quota_exempt.set(True)
    try:
        assert (await client.generate("test", {}, Answer)).answer == "合成回答"
        assert client.budget.calls == 1 and len(calls) == 1
    finally:
        quota_exempt.reset(token)
    try:
        with pytest.raises(RuntimeError, match="model_limit"):
            await client.generate("test", {}, Answer)
        assert len(calls) == 1
    finally:
        await client.close()
