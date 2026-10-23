"""Real LangChain/OpenAI SDK over a controlled in-process provider transport.

Only the provider is replaced. Each response is authored as independent wire
chunks, with a pause before the tail; no completed answer is split for playback.
"""
import asyncio
import json
import httpx
from openai import AsyncOpenAI
from config import Settings
from llm_client import ModelClient
from main import create_app


class ProviderStream(httpx.AsyncByteStream):
    def __init__(self, chunks, delay=0.6):
        self.chunks, self.delay = chunks, delay

    async def __aiter__(self):
        for index, content in enumerate(self.chunks):
            if index:
                await asyncio.sleep(self.delay)
            event = {"id": "fixture", "object": "chat.completion.chunk", "created": 0, "model": "fixture",
                     "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}]}
            yield ("data: " + json.dumps(event) + "\n\n").encode()
        yield b'data: [DONE]\n\n'


def provider(request):
    body = json.loads(request.content)
    payload = json.loads(body["messages"][1]["content"])
    text = payload.get("input", payload.get("instruction", ""))
    if not body.get("stream"):
        action = "DOCUMENT_UPDATE" if "修改" in text else "DOCUMENT_CREATE" if "创建" in text else "KNOWLEDGE_QA"
        result = {"action": action, "standaloneQuery": text, "conditionPatch": {}}
        if "它们" in text:
            result["standaloneQuery"] = "进程与线程共享哪些资源"
        return httpx.Response(200, json={"id": "fixture", "object": "chat.completion", "created": 0, "model": "fixture",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": json.dumps(result)}, "finish_reason": "stop"}]})
    if "instruction" in payload:
        chunks = ['{"title":"学习笔记","content":"# 线程笔记\\n', '同一进程的线程共享地址空间。"}']
    else:
        source = "fake-source" if "非法引用" in text else "os-threads#0"
        chunks = ['{"answer":"线程共享', '地址空间，保留各自的栈。","sourceIds":["' + source + '"]}']
    return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=ProviderStream(chunks, 120 if "等待停止" in text else 0.6))


settings = Settings(_env_file=None, LLM_ENABLED=True, LLM_API_KEY="test-only", RAG_BACKEND="lexical")
model = ModelClient(settings)
model.client = AsyncOpenAI(api_key="test-only", base_url="https://provider.invalid/v1", max_retries=0,
    http_client=httpx.AsyncClient(transport=httpx.MockTransport(provider)))
app = create_app(settings, model=model)

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    # Fixture diagnostics contain field names only, never request data.
    print("fixtureValidation", [(item["loc"],item["type"]) for item in error.errors()], flush=True)
    return JSONResponse(status_code=422,content={"error":"invalid_fixture_request"})
