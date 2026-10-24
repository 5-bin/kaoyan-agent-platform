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
# An isolated embedded index with explicit vectors exercises the HTTP contract.
# It does not measure real model quality or download model files during tests.
from tempfile import TemporaryDirectory
from question_search import QuestionIndex
from tests.question_fixture import ContractEncoder
question_folder = TemporaryDirectory(prefix="question-wire-index-")
settings.QUESTION_INDEX = __import__('pathlib').Path(question_folder.name)
app = create_app(settings, model=model, question_index=QuestionIndex(settings, encoder=ContractEncoder()))

# Deliberately malformed upstream envelopes exercise Java's trust boundary.
# These routes exist only in this isolated fixture, never in main.create_app.
from fastapi.responses import StreamingResponse
from schemas import ConversationResolution


@app.middleware("http")
async def source_policy_fixture(request, call_next):
    paths = {"/internal/rag/conversation/plan", "/internal/rag/conversation/stream", "/internal/rag/chat"}
    if request.url.path not in paths or request.headers.get("X-Internal-Key") != settings.AGENT_INTERNAL_KEY:
        return await call_next(request)
    body = await request.json()
    text = body.get("userInput", "")
    if not text.startswith("source-policy-fixture:"):
        return await call_next(request)
    mode = text.split(":", 1)[1]
    if request.url.path.endswith("/plan"):
        if mode == "plan":
            return JSONResponse({"action": "INVALID"})
        return JSONResponse(ConversationResolution(action="KNOWLEDGE_QA", standaloneQuery=text).model_dump(by_alias=True))
    host = {"github": "github.com", "mit": "ocw.mit.edu", "school": "yzb.buaa.edu.cn"}.get(mode, "github.com")
    if mode == "denied":
        host = "github.com.attacker.invalid"
    reference = {"id": "fixture-source#0", "url": f"https://{host}/PRIVATE_URL_MARKER",
                 "version": "fixture-v1", "title": "合成来源", "locator": "合成位置",
                 "retrievedAt": "2026-10-24", "excerpt": "合成摘录"}
    release = app.state.engine.corpus.release_id
    result = {"answer": "合成引用校验回答", "outcome": "COMPLETED", "explanationMode": "rules",
              "resolvedTaskType": body["taskType"], "releaseId": release, "conditions": {}}
    if mode == "result":
        result["releaseId"] = "rag-v1-0000000000000000"
    if mode == "conditions":
        result["conditions"] = {"examYear": "PRIVATE_CONDITION_MARKER"}
    if mode == "document":
        result["documentProposal"] = {"title": "", "content": "PRIVATE_DOCUMENT_MARKER"}
    response = {"taskId": body["taskId"], "status": "SUCCESS", "releaseId": release,
                "references": [reference], "result": result}
    if request.url.path.endswith("/chat"):
        return JSONResponse(response)
    if mode == "upstream":
        return JSONResponse({"error": "PRIVATE_UPSTREAM_MARKER"}, status_code=503)
    async def event():
        yield "data: " + json.dumps({"type": "result", "response": response}) + "\n\n"
    return StreamingResponse(event(), media_type="text/event-stream")

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    # Fixture diagnostics contain field names only, never request data.
    print("fixtureValidation", [(item["loc"],item["type"]) for item in error.errors()], flush=True)
    return JSONResponse(status_code=422,content={"error":"invalid_fixture_request"})
