"""uvicorn main:create_app --factory --host 127.0.0.1 --port 8001"""

import asyncio
import json
import logging
import re
import secrets
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from config import PLAN_FALLBACK_SECONDS, Settings, provider_identifier
from conversation import ConversationWorkflow
from core.admission_client import AdmissionLinksTool, McpAdmissionClient
from core.mcp_client import McpKnowledgeClient, McpKnowledgeSearchTool
from core.mcp_runtime import McpErrorCode, McpState, McpStatus
from core.runtime import CallBudget, admission_budget, execution_budget, retrieval_budget
from llm_client import ModelClient, quota_exempt, request_model_calls, stream_sink
from question_search import IndexRequest, QuestionIndex, SearchRequest
from retrieval import Corpus, Retriever
from schemas import ChatRequest, ChatResponse, ConversationRequest
from workflows import Workflows

log = logging.getLogger(__name__)


def create_app(settings=None, model=None, retriever=None, question_index=None):
    settings = settings or Settings()
    corpus = Corpus(settings.RAG_DATA, settings.RAG_SOURCE_POLICY_FILE)
    model = model or ModelClient(settings)
    # Serving never downloads embedding weights; ingest.py prepares them.
    retriever = retriever or Retriever(settings, corpus, local_files_only=True)
    mcp_client = None
    knowledge_search = None
    if settings.KNOWLEDGE_TOOL_TRANSPORT == "mcp_stdio":
        mcp_client = McpKnowledgeClient(settings, corpus)
        knowledge_search = McpKnowledgeSearchTool(mcp_client)
    admission_client = None
    admission_status = McpStatus(False, McpState.DISABLED)
    if settings.ADMISSION_MCP_ENABLED:
        try:
            admission_client = McpAdmissionClient()
        except (OSError, ValueError) as error:
            # A broken registry disables only link lookup; the Agent still starts.
            log.warning("admissionMcpConfigFailure=%s", type(error).__name__)
            admission_status = McpStatus(True, McpState.UNAVAILABLE, McpErrorCode.START_FAILED)
    admission_tool = AdmissionLinksTool(admission_client) if admission_client is not None else None
    engine = Workflows(settings, corpus, retriever, model, knowledge_search, admission_tool)
    conversation = ConversationWorkflow(engine)
    question_index = question_index or QuestionIndex(settings)

    @asynccontextmanager
    async def lifespan(app):
        try:
            async with AsyncExitStack() as stack:
                if mcp_client is not None:
                    await stack.enter_async_context(mcp_client.connect(isolate_failure=True))
                if admission_client is not None:
                    await stack.enter_async_context(admission_client.connect(isolate_failure=True))
                yield
        finally:
            await model.close()
            retriever.close()
            await asyncio.to_thread(question_index.close)

    app = FastAPI(
        title="考研RAG内部服务",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.engine = engine
    app.state.question_index = question_index
    app.state.mcp_client = mcp_client
    app.state.admission_client = admission_client

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "loc": list(item["loc"]),
                        "type": item["type"],
                        "msg": "请求字段不符合契约",
                    }
                    for item in error.errors()
                ]
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.middleware("http")
    async def private_response(request, call_next):
        exemption_token = quota_exempt.set(False)
        token = request_model_calls.set(0)
        budget_token = execution_budget.set(CallBudget(2))
        admission_token = admission_budget.set(CallBudget(1))
        retrieval_token = retrieval_budget.set(CallBudget(3))
        try:
            response = await call_next(request)
        finally:
            request_model_calls.reset(token)
            execution_budget.reset(budget_token)
            quota_exempt.reset(exemption_token)
            retrieval_budget.reset(retrieval_token)
            admission_budget.reset(admission_token)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    async def authenticate(x_internal_key: str = Header(default="")):
        if not secrets.compare_digest(
            x_internal_key.encode(), settings.AGENT_INTERNAL_KEY.encode()
        ):
            raise HTTPException(401, "invalid internal key")

    @app.get("/health")
    async def health():
        provider = provider_identifier(settings.LLM_BASE_URL)
        return {
            "status": "ok",
            "releaseId": corpus.release_id,
            "retrievalBackend": settings.RAG_BACKEND,
            "modelEnabled": settings.LLM_ENABLED,
            "admissionMcpEnabled": settings.ADMISSION_MCP_ENABLED,
            "mcpTools": {
                "knowledge": (mcp_client.status if mcp_client is not None else
                              McpStatus(False, McpState.DISABLED)).snapshot(),
                "admission": (admission_client.status if admission_client is not None else
                              admission_status).snapshot(),
            },
            "provider": provider,
        }

    @app.post("/internal/rag/questions/index", dependencies=[Depends(authenticate)])
    async def question_index_submit(req: IndexRequest):
        return await asyncio.to_thread(question_index.submit, req.questions)

    @app.get(
        "/internal/rag/questions/index/{release_id}",
        dependencies=[Depends(authenticate)],
    )
    async def question_index_status(release_id: str):
        if not re.fullmatch("questions-[a-f0-9]{32}", release_id):
            raise HTTPException(422, "invalid release")
        return await asyncio.to_thread(question_index.status, release_id)

    @app.post("/internal/rag/questions/search", dependencies=[Depends(authenticate)])
    async def question_search(req: SearchRequest):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(question_index.search, req), timeout=12
            )
        except Exception as error:
            log.warning("questionSearchFailure=%s", type(error).__name__)
            raise HTTPException(503, "题目语义检索暂时不可用。") from None

    @app.post("/internal/rag/conversation/plan", dependencies=[Depends(authenticate)])
    async def conversation_plan(req: ConversationRequest):
        quota_exempt.set(req.quotaExempt)
        plan_token = execution_budget.set(CallBudget(1))
        try:
            # The parser has its own deadline and local fallback; leave room for
            # that fallback instead of expiring at the same instant (Java waits 22s).
            plan = await asyncio.wait_for(
                conversation.plan(req),
                timeout=settings.CONVERSATION_PARSE_TIMEOUT + PLAN_FALLBACK_SECONDS,
            )
            output = plan.model_dump(by_alias=True)
            # A patch must retain omitted fields across Java's plan/stream checkpoint.
            output["conditionPatch"] = plan.conditionPatch.model_dump(
                by_alias=True, exclude_unset=True
            )
            return output
        except Exception as error:
            log.warning("planFailure=%s", type(error).__name__)
            raise HTTPException(503, "请求解析暂时不可用，请稍后重试。") from None
        finally:
            execution_budget.reset(plan_token)

    @app.post(
        "/internal/rag/chat",
        response_model=ChatResponse,
        dependencies=[Depends(authenticate)],
    )
    async def chat(req: ChatRequest):
        quota_exempt.set(req.quotaExempt)
        try:
            result = await asyncio.wait_for(engine.run(req), timeout=settings.AGENT_TASK_TIMEOUT)
            if not isinstance(result, dict) or result.get("outcome") not in {
                "COMPLETED",
                "NEEDS_INPUT",
                "UNSUPPORTED",
            }:
                raise ValueError("invalid_workflow_result")
            return ChatResponse(
                taskId=req.taskId,
                status="SUCCESS",
                result=result,
                references=result["references"],
                releaseId=corpus.release_id,
            )
        except Exception as e:
            log.warning("task=%s failure=%s", req.taskId, type(e).__name__)
            return ChatResponse(
                taskId=req.taskId,
                status="FAILED",
                releaseId=corpus.release_id,
                errorMessage="检索或处理暂时不可用，请按任务编号检查服务日志。",
            )

    @app.post("/internal/rag/conversation/stream", dependencies=[Depends(authenticate)])
    async def conversation_stream(req: ConversationRequest):
        quota_exempt.set(req.quotaExempt)

        async def events():
            plan = req.preparedPlan
            admission_token = admission_budget.set(CallBudget(1))
            retrieval_token = retrieval_budget.set(CallBudget(3))
            budget_token = execution_budget.set(
                CallBudget(
                    4 if plan and plan.planVersion == 2 else 2,
                    plan.modelCallsUsed if plan else 0,
                )
            )
            queue = asyncio.Queue(maxsize=64)

            async def run():
                token = stream_sink.set(queue.put)
                try:
                    await queue.put(
                        {"type": "stage", "stage": "正在理解问题与检索资料"}
                    )
                    result = await asyncio.wait_for(conversation.run(req), timeout=settings.AGENT_TASK_TIMEOUT)
                    response = ChatResponse(
                        taskId=req.taskId,
                        status="SUCCESS",
                        result=result,
                        references=result["references"],
                        releaseId=corpus.release_id,
                    )
                    await queue.put(
                        {"type": "result", "response": response.model_dump()}
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    log.warning(
                        "task=%s conversationFailure=%s",
                        req.taskId,
                        type(error).__name__,
                    )
                    await queue.put(
                        {"type": "error", "message": "生成失败或超时，请重试。"}
                    )
                finally:
                    stream_sink.reset(token)

            worker = asyncio.create_task(run())
            try:
                while True:
                    event = await queue.get()
                    yield ("data: " + json.dumps(event, ensure_ascii=False) + "\n\n")
                    if event["type"] in ("result", "error"):
                        break
            finally:
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
                execution_budget.reset(budget_token)
                retrieval_budget.reset(retrieval_token)
                admission_budget.reset(admission_token)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store"},
        )

    return app
