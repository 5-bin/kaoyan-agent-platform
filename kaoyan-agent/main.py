"""uvicorn main:create_app --factory --host 127.0.0.1 --port 8001"""
import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException
from config import Settings
from llm_client import ModelClient
from retrieval import Corpus, Retriever
from schemas import ChatRequest, ChatResponse
from workflows import Workflows

log = logging.getLogger(__name__)


def create_app(settings=None, model=None, retriever=None):
    settings = settings or Settings()
    corpus = Corpus(settings.RAG_DATA)
    model = model or ModelClient(settings)
    retriever = retriever or Retriever(settings, corpus)
    engine = Workflows(settings, corpus, retriever, model)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await model.close()
        retriever.close()

    app = FastAPI(title="考研RAG内部服务", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.engine = engine

    async def authenticate(x_internal_key: str = Header(default="")):
        if not secrets.compare_digest(x_internal_key.encode(), settings.AGENT_INTERNAL_KEY.encode()):
            raise HTTPException(401, "invalid internal key")

    @app.get("/health")
    async def health():
        return {"status": "ok", "releaseId": corpus.release_id, "retrievalBackend": settings.RAG_BACKEND,
                "modelEnabled": settings.LLM_ENABLED}

    @app.post("/internal/rag/chat", response_model=ChatResponse, dependencies=[Depends(authenticate)])
    async def chat(req: ChatRequest):
        try:
            result = await asyncio.wait_for(engine.run(req), timeout=42)
            return ChatResponse(taskId=req.taskId, status="SUCCESS", result=result,
                references=result["references"], releaseId=corpus.release_id)
        except Exception as e:
            # Never echo provider exception bodies, URLs, tokens or database errors.
            log.warning("task=%s failure=%s", req.taskId, type(e).__name__)
            return ChatResponse(taskId=req.taskId, status="FAILED", releaseId=corpus.release_id,
                errorMessage="检索或处理暂时不可用，请按任务编号检查服务日志。")

    return app
