"""Exact wire/presentation compatibility with the frozen LangChain adapter."""

import json
import copy
from pathlib import Path
import httpx
import pytest
from openai import AsyncOpenAI
from config import Settings
from llm_client import ModelClient, stream_sink
from schemas import Answer
from tests.chat_wire_app import ProviderStream

CASES = json.loads(
    (Path(__file__).parent / "fixtures/provider-baseline.json").read_text()
)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES)
async def test_frozen_provider_wire(case):
    sent, events = [], []

    def provider(req):
        body = json.loads(req.content)
        sent.append(body)
        if body.get("stream"):
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=ProviderStream(
                    ['{"answer":"合成', '回答","sourceIds":["s"]}'], 0
                ),
            )
        return httpx.Response(
            200,
            json={
                "id": "synthetic",
                "object": "chat.completion",
                "created": 0,
                "model": "fixture",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": '{"answer":"合成回答","sourceIds":["s"]}',
                        },
                    }
                ],
            },
        )

    config = Settings(
        _env_file=None,
        AGENT_INTERNAL_KEY="synthetic-key-12345678",
        LLM_ENABLED=True,
        LLM_API_KEY="synthetic",
        LLM_BASE_URL="https://provider.invalid/v1",
        LLM_MODEL_MAIN="main",
        LLM_MODEL_ROUTER="router",
        LLM_THINKING_MODE=case["thinking"],
    )
    client = ModelClient(config)
    client.client = AsyncOpenAI(
        api_key="synthetic",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(provider)),
    )

    async def sink(event):
        events.append(event)

    token = stream_sink.set(sink if case["streaming"] else None)
    try:
        answer = await client.generate(
            "合成指令", {"input": "合成输入"}, Answer, router=case["router"]
        )
        expected = copy.deepcopy(case["request"])
        # The approved budget contract changes router output allowance and JSON
        # whitespace only; retain every other frozen transport assertion.
        expected["max_completion_tokens"] = 2048 if case["router"] else 2200
        expected["messages"][1]["content"] = json.dumps(
            json.loads(expected["messages"][1]["content"]), ensure_ascii=False, separators=(",", ":")
        )
        assert sent == [expected]
        assert events == case["events"]
        assert answer.model_dump() == case["answer"]
    finally:
        stream_sink.reset(token)
        await client.close()
