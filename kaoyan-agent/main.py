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
import asyncio
import secrets

from fastapi import FastAPI, Header, HTTPException, Depends

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


async def require_internal_key(x_internal_key: str = Header(default="")):
    if not secrets.compare_digest(x_internal_key.encode(), settings.AGENT_INTERNAL_KEY.encode()):
        raise HTTPException(status_code=401, detail="内部认证失败")


@app.post("/internal/rag/chat", response_model=ChatResponse, dependencies=[Depends(require_internal_key)])
async def chat(req: ChatRequest):
    start = time.time()
    try:
        async with asyncio.timeout(40):
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

        if not isinstance(result, dict) or not result:
            raise ValueError("Agent结果缺失")
        # 尚未接入可追溯资料集合，不能把模型自造引用当成证据。
        if result.get("references"):
            raise ValueError("引用缺少可验证来源")
        required = "summary" if req.taskType in {"PRACTICE_SUMMARY", "SCHOOL_RECOMMEND"} else "answer"
        if req.taskType != "CHAT" and (
            not isinstance(result.get(required), str)
            or not result[required].strip() or len(result[required]) > 20000
        ):
            raise ValueError("Agent结果字段不正确")
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
        logger.warning("taskId=%s failureType=%s", req.taskId, type(e).__name__)
        return ChatResponse(taskId=req.taskId, status="FAILED", errorMessage="Agent未完成任务，请检查配置或稍后重试")
