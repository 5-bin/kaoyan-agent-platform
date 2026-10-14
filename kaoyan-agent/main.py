"""考研 Agent 服务入口。

启动：
    python3.12 -m venv .venv
    # Windows: py -3.12 -m venv .venv && .venv\\Scripts\\activate
    pip install -r requirements.txt
    cp .env.example .env   # 编辑填 AGENT_INTERNAL_KEY / DB_PASSWORD / LLM_API_KEY
    uvicorn main:app --host 0.0.0.0 --port 8001 --reload
"""
import logging
import time

from fastapi import FastAPI, Request

from config import settings
from schemas import ChatRequest, ChatResponse
from router import route
from handlers import summary, wenda, tuijian, changui

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("agent")

app = FastAPI(title="考研 Agent 服务")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/internal/rag/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    start = time.time()
    key = request.headers.get("X-Internal-Key", "")
    if key != settings.AGENT_INTERNAL_KEY:
        return ChatResponse(taskId=req.taskId, status="FAILED", errorMessage="invalid internal key")

    if not req.taskId:
        return ChatResponse(taskId="", status="FAILED", errorMessage="taskId required")

    try:
        result: dict
        intent = ""
        if req.taskType == "PRACTICE_SUMMARY":
            result = await summary.handle(req)
        elif req.taskType == "SCHOOL_RECOMMEND":
            intent = "TUIJIAN_YUANXIAO"
            result = await tuijian.handle(req.userInput or "", req.profile, req.messages or [])
        elif req.taskType == "KNOWLEDGE_QA":
            intent = "ZHISHI_WENDA"
            result = await wenda.handle(req.userInput or "", req.profile, req.messages or [])
        else:
            routed = await route(req.userInput or "", req.messages or [])
            intent = routed.get("intent", "CHANGUI")
            if intent == "TUIJIAN_YUANXIAO":
                result = await tuijian.handle(req.userInput or "", req.profile, req.messages or [])
            elif intent == "ZHISHI_WENDA":
                result = await wenda.handle(req.userInput or "", req.profile, req.messages or [])
            else:
                result = await changui.handle(req.userInput or "", req.profile, req.messages or [])

        logger.info(
            "taskId=%s intent=%s costMs=%d",
            req.taskId, intent, int((time.time() - start) * 1000),
        )
        return ChatResponse(
            taskId=req.taskId,
            status="SUCCESS",
            result=result,
            references=result.get("references", []) if isinstance(result, dict) else [],
        )
    except Exception as e:
        logger.exception("taskId=%s failed", req.taskId)
        return ChatResponse(taskId=req.taskId, status="FAILED", errorMessage=str(e))
