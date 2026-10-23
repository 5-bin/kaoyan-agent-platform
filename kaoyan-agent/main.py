"""uvicorn main:create_app --factory --host 127.0.0.1 --port 8001"""
import asyncio
import logging
import secrets
import json
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from config import Settings, provider_identifier
from llm_client import ModelClient
from retrieval import Corpus, Retriever
from schemas import ChatRequest, ChatResponse
from workflows import Workflows
from schemas import ConversationRequest
from conversation import ConversationWorkflow
from llm_client import stream_sink, request_model_calls, quota_exempt
from langsmith.run_helpers import tracing_context

log = logging.getLogger(__name__)


def create_app(settings=None, model=None, retriever=None):
    settings = settings or Settings()
    corpus = Corpus(settings.RAG_DATA)
    model = model or ModelClient(settings)
    retriever = retriever or Retriever(settings, corpus)
    engine = Workflows(settings, corpus, retriever, model)
    conversation = ConversationWorkflow(engine)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await model.close()
        retriever.close()

    app = FastAPI(title="考研RAG内部服务", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.engine = engine

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # FastAPI's default errors include rejected values and may include full
        # personal records. Keep only stable field locations and error classes.
        return JSONResponse(status_code=422, content={"detail": [
            {"loc": list(item["loc"]), "type": item["type"], "msg": "请求字段不符合契约"}
            for item in error.errors()]}, headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def private_response(request, call_next):
        exemption_token = quota_exempt.set(False)
        token = request_model_calls.set(0)
        try:
            with tracing_context(enabled=False):
                response = await call_next(request)
        finally:
            request_model_calls.reset(token)
            quota_exempt.reset(exemption_token)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    async def authenticate(x_internal_key: str = Header(default="")):
        if not secrets.compare_digest(x_internal_key.encode(), settings.AGENT_INTERNAL_KEY.encode()):
            raise HTTPException(401, "invalid internal key")

    @app.get("/health")
    async def health():
        provider = provider_identifier(settings.LLM_BASE_URL)
        return {"status": "ok", "releaseId": corpus.release_id, "retrievalBackend": settings.RAG_BACKEND,
                "modelEnabled": settings.LLM_ENABLED, "provider": provider}

    @app.post("/internal/rag/conversation/plan", dependencies=[Depends(authenticate)])
    async def conversation_plan(req: ConversationRequest):
        quota_exempt.set(req.quotaExempt)
        try:
            plan = await asyncio.wait_for(conversation.plan(req), timeout=20)
            return plan.model_dump(by_alias=True)
        except Exception as error:
            log.warning("planFailure=%s", type(error).__name__)
            raise HTTPException(503, "请求解析暂时不可用，请稍后重试。") from None

    @app.post("/internal/rag/chat", response_model=ChatResponse, dependencies=[Depends(authenticate)])
    async def chat(req: ChatRequest):
        quota_exempt.set(req.quotaExempt)
        try:
            result = await asyncio.wait_for(engine.run(req), timeout=42)
            if not isinstance(result, dict) or result.get("outcome") not in {"COMPLETED", "NEEDS_INPUT", "UNSUPPORTED"}:
                raise ValueError("invalid_workflow_result")
            return ChatResponse(taskId=req.taskId, status="SUCCESS", result=result,
                references=result["references"], releaseId=corpus.release_id)
        except Exception as e:
            # Never echo provider exception bodies, URLs, tokens or database errors.
            log.warning("task=%s failure=%s", req.taskId, type(e).__name__)
            return ChatResponse(taskId=req.taskId, status="FAILED", releaseId=corpus.release_id,
                errorMessage="检索或处理暂时不可用，请按任务编号检查服务日志。")

    @app.post("/internal/rag/conversation/stream", dependencies=[Depends(authenticate)])
    async def conversation_stream(req: ConversationRequest):
        quota_exempt.set(req.quotaExempt)
        async def events():
            queue = asyncio.Queue(maxsize=64)
            async def run():
                token = stream_sink.set(queue.put)
                try:
                    await queue.put({"type": "stage", "stage": "正在理解问题与检索资料"})
                    result = await asyncio.wait_for(conversation.run(req), timeout=42)
                    response = ChatResponse(taskId=req.taskId, status="SUCCESS", result=result,
                        references=result["references"], releaseId=corpus.release_id)
                    await queue.put({"type": "result", "response": response.model_dump()})
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    log.warning("task=%s conversationFailure=%s", req.taskId, type(error).__name__)
                    await queue.put({"type": "error", "message": "生成失败或超时，请重试。"})
                finally:
                    stream_sink.reset(token)
            worker = asyncio.create_task(run())
            try:
                while True:
                    event = await queue.get()
                    yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                    if event["type"] in ("result", "error"):
                        break
            finally:
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    return app
