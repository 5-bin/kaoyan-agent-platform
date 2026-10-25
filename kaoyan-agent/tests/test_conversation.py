import asyncio
import json
from unittest.mock import AsyncMock
import pytest
import httpx
from openai import AsyncOpenAI
from fastapi.testclient import TestClient
from config import Settings
from main import create_app
from schemas import ConversationRequest, ConversationResolution, Answer
from conversation import ConversationWorkflow
from workflows import Workflows
from retrieval import Corpus, Retriever
from llm_client import ModelClient, stream_sink
from tests.chat_wire_app import provider

KEY = "test-only-internal-key-123456"


def request(**changes):
    return ConversationRequest(taskId="conversation-test", userId=1, taskType="CHAT", userInput="进程与线程", **changes)


def workflow(enabled=False):
    settings = Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY, LLM_ENABLED=enabled, LLM_API_KEY="test-only" if enabled else "")
    corpus = Corpus(settings.RAG_DATA)
    engine = Workflows(settings, corpus, Retriever(settings, corpus), AsyncMock())
    return ConversationWorkflow(engine)


@pytest.mark.asyncio
async def test_followup_rewrites_before_retrieval_and_topic_switch_does_not_reuse_subject():
    flow = workflow()
    req = request(messages=[{"role":"user","content":"进程与线程"},{"role":"assistant","content":"共享地址空间"}])
    req.userInput = "它们共享哪些资源"
    result = await flow.run(req)
    assert "进程与线程" in result["standaloneQuery"]
    assert result["references"][0]["id"] == "os-threads#0"
    req.userInput = "TCP可靠传输"
    result = await flow.run(req)
    assert result["standaloneQuery"] == "TCP可靠传输"
    assert all("os-threads" not in ref["id"] for ref in result["references"])


@pytest.mark.asyncio
async def test_accumulated_conditions_override_only_session_and_filter_candidates():
    flow = workflow()
    req = request(profile={"examYear":2026,"targetMajor":"085404"})
    for text in ("择校2027年", "081200学硕", "只考虑江苏"):
        req.userInput = text
        result = await flow.run(req)
    assert req.conditions.examYear == 2027
    assert result["candidates"][0]["region"] == "江苏"
    assert len(result["candidates"]) == 1
    req.userInput = "改为北京地区"
    result = await flow.run(req)
    assert result["conditions"]["regions"] == ["北京"]


@pytest.mark.asyncio
async def test_ambiguous_reference_and_missing_document_ask_for_input():
    flow = workflow()
    req=request(); req.userInput="它们是什么"
    assert (await flow.run(req))["outcome"] == "NEEDS_INPUT"
    req.userInput="修改这份笔记"
    result=await flow.run(req)
    assert result["outcome"] == "NEEDS_INPUT" and "选择" in result["answer"]


@pytest.mark.asyncio
async def test_disabled_model_does_not_fake_document_generation():
    req=request(); req.userInput="创建一份学习计划"
    result=await workflow().run(req)
    assert result["outcome"] == "UNSUPPORTED" and "documentProposal" not in result


@pytest.mark.asyncio
async def test_bad_resolution_is_rejected_without_model_retry():
    flow=workflow(enabled=True)
    flow.engine.model.generate.side_effect=ValueError("bad resolution")
    with pytest.raises(ValueError): await flow.run(request(privacy={"modelAllowed":True,"provider":"https://open.bigmodel.cn/api/paas/v4"}))
    flow.engine.model.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_unresolved_chat_asks_without_another_router_call():
    flow=workflow(enabled=True)
    flow.engine.model.generate.return_value=ConversationResolution(action="CHAT",standaloneQuery="不明确的请求")
    assert (await flow.run(request(privacy={"modelAllowed":True,"provider":"https://open.bigmodel.cn/api/paas/v4"})))["outcome"] == "NEEDS_INPUT"
    flow.engine.model.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_real_langchain_sdk_projects_before_provider_stream_finishes():
    settings=Settings(_env_file=None,AGENT_INTERNAL_KEY=KEY,LLM_ENABLED=True,LLM_API_KEY="test-only")
    model=ModelClient(settings)
    model.client=AsyncOpenAI(api_key="test-only",max_retries=0,http_client=httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    seen=asyncio.Event(); events=[]
    async def collect(event): events.append(event); seen.set()
    token=stream_sink.set(collect)
    task=asyncio.create_task(model.generate("知识问答",{"input":"进程与线程"},Answer))
    try:
        await asyncio.wait_for(seen.wait(),2)
        assert not task.done()
        assert events[0]["text"] == "线程共享"
        answer=await task
        assert answer.answer == "线程共享地址空间，保留各自的栈。"
        assert "".join(event["text"] for event in events) == answer.answer
    finally:
        stream_sink.reset(token); await model.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("chunks", [
    ['{"answer":"中', '文\\n转义\\"', '引号\\"","sourceIds":["s"]}'],
    ['{"answer":"\\u4', 'e2d\\u6587', '","sourceIds":["s"]}'],
    ['{"answer":"😀', '中文\\\\路径","sourceIds":["s"]}'],
])
async def test_projection_handles_unicode_escaping_and_cross_chunk_json(chunks):
    from tests.chat_wire_app import ProviderStream
    model=ModelClient(Settings(_env_file=None,AGENT_INTERNAL_KEY=KEY,LLM_ENABLED=True,LLM_API_KEY="test-only"))
    model.client=AsyncOpenAI(api_key="test-only",max_retries=0,http_client=httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req:httpx.Response(200,headers={"content-type":"text/event-stream"},stream=ProviderStream(chunks,0)))))
    events=[]
    async def collect(event): events.append(event)
    token=stream_sink.set(collect)
    try:
        answer=await model.generate("测试",{},Answer)
        assert "".join(event["text"] for event in events)==answer.answer
        offset=0
        for event in events:
            assert event["offset"]==offset; offset+=len(event["text"])
    finally: stream_sink.reset(token); await model.close()


def test_stream_auth_and_schema_validation():
    with TestClient(create_app(Settings(_env_file=None,AGENT_INTERNAL_KEY=KEY))) as client:
        body=request().model_dump()
        assert client.post("/internal/rag/conversation/stream",json=body).status_code==401
        body["conditions"]={"degreeType":"wrong"}
        assert client.post("/internal/rag/conversation/stream",json=body,headers={"X-Internal-Key":KEY}).status_code==422
