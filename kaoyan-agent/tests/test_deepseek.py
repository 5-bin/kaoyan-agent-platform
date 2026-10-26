"""Verify SDK wire payloads with a local transport; never contact a provider."""
import json
import httpx
import pytest
from openai import AsyncOpenAI
from config import Settings
from schemas import TutorExplanation
from llm_client import ModelClient
import llm_client


@pytest.mark.asyncio
@pytest.mark.parametrize("base,model_name,router,mode,expected_thinking", [
    ("https://api.deepseek.com", "deepseek-flash", False, "default", "disabled"),
    ("https://api.deepseek.com/v1", "deepseek-flash", False, "default", "disabled"),
    ("https://api.deepseek.com", "deepseek-flash", True, "default", "disabled"),
    ("https://api.deepseek.com.example.test", "deepseek-flash", False, "default", None),
    ("https://open.bigmodel.cn/api/paas/v4", "glm-4-plus", False, "default", None),
    ("https://gateway.example.test/v1", "deepseek-flash", False, "default", None),
    ("https://api.deepseek.com", "deepseek-flash", False, "enabled", "enabled"),
    ("https://api.deepseek.com", "deepseek-flash", True, "disabled", "disabled"),
])
async def test_flash_options_are_scoped_to_official_endpoint(monkeypatch, base, model_name, router, mode, expected_thinking):
    requests = []
    def respond(req):
        requests.append(req)
        return httpx.Response(200, json={"id": "test-completion", "object": "chat.completion", "created": 0,
            "model": model_name, "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"explanation": "已保存版本的解释", "standardAnswer": "B"})}}]})
    monkeypatch.setattr(llm_client, "AsyncOpenAI", lambda **kwargs: AsyncOpenAI(**kwargs,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))))
    settings = Settings(_env_file=None, AGENT_INTERNAL_KEY="test-only-internal-key-123456", LLM_ENABLED=True,
        LLM_API_KEY="test-only", LLM_BASE_URL=base, LLM_MODEL_MAIN="unused" if router else model_name,
        LLM_MODEL_ROUTER=model_name, LLM_THINKING_MODE=mode)
    client = ModelClient(settings)
    try:
        result = await client.generate("只返回JSON。", {"query": "为什么选B", "answer": "B"}, TutorExplanation, router=router)
        assert result.standardAnswer == "B"
        assert len(requests) == 1
        sent = json.loads(requests[0].content)
        assert sent["model"] == model_name
        assert sent["response_format"] == {"type": "json_object"}
        assert sent["max_completion_tokens"] == 2200
        assert [m["role"] for m in sent["messages"]] == ["system", "user"]
        if expected_thinking:
            assert sent["thinking"] == {"type": expected_thinking}
        else:
            assert "thinking" not in sent
    finally:
        await client.close()
