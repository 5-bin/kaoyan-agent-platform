"""Native framework, compound execution, privacy, and cancellation regressions."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from pydantic import ValidationError

from agents.base import StructuredAgent
from agents.coordinator import ConversationCoordinator
from agents.learning import LearningAgent
from agents.planning import local_orchestration
from config import Settings
from core.context import AuthorizedContextBuilder
from core.errors import ToolUnavailable
from core.framework import Agent, Tool, ToolRegistry
from core.model import AsyncHelloAgentsLLM
from core.runtime import CallBudget, execution_budget, phase_budget
from llm_client import ModelClient, stream_sink
from main import create_app
from schemas import Answer, ConversationRequest, ConversationResolution
from tests.test_conversation import workflow
from tests.test_workflows import KEY
from tools.knowledge import KnowledgeSearchTool
from tools.registry import EmptyParameters, StrictToolRegistry, ValidatedTool


def request(text, **kwargs):
    return ConversationRequest.model_validate(
        {
            "taskId": "multi-test",
            "userId": 1,
            "taskType": "CHAT",
            "userInput": text,
            **kwargs,
        }
    )


@pytest.mark.asyncio
async def test_native_framework_is_used_and_request_history_is_released(monkeypatch):
    assert issubclass(StructuredAgent, Agent)
    assert issubclass(KnowledgeSearchTool, Tool)
    assert issubclass(StrictToolRegistry, ToolRegistry)
    flow = workflow()
    recorded = []
    original = Agent.add_message

    def record(self, message):
        recorded.append((id(self), message.role))
        return original(self, message)

    monkeypatch.setattr(Agent, "add_message", record)
    coordinator = ConversationCoordinator(flow.engine)
    result = await coordinator.execute(request("进程与线程"))
    assert result["references"]
    assert len({item[0] for item in recorded}) >= 2
    assert {item[1] for item in recorded} == {"user", "assistant"}
    assert coordinator.get_history() == []


@pytest.mark.asyncio
async def test_local_compound_plan_keeps_rules_and_does_not_call_models():
    flow = workflow()
    req = request(
        "分析薄弱点，安排7天复习计划，并推荐院校",
        conditions={
            "examYear": 2027,
            "majorCodes": ["081200"],
            "degreeType": "academic",
        },
        learningContext={
            "statistics": {
                "questionCount": 3,
                "correctCount": 1,
                "knowledgePoints": [{"knowledgePoint": "线程", "questionCount": 3}],
            }
        },
    )
    plan = await flow.plan(req)
    assert plan.planVersion == 2
    assert [step.agent for step in plan.steps] == ["LEARNING", "STUDY_PLAN", "SCHOOL"]
    req.preparedPlan = plan
    result = await flow.run(req)
    assert len(result["studyPlan"]["days"]) == 7
    assert result["studyPlan"]["days"][0]["topic"] == "线程"
    assert len(result["candidates"]) == 3
    assert "documentProposal" not in result
    flow.engine.model.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_rule_plan_can_become_a_confirmable_note_without_model_access():
    flow = workflow()
    result = await flow.run(request("安排3天复习计划，并保存成笔记"))
    assert len(result["studyPlan"]["days"]) == 3
    assert "第3天" in result["documentProposal"]["content"]
    assert result["documentProposal"]["operation"] == "create"
    assert "确认" in result["answer"]
    flow.engine.model.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_study_plan_appends_to_selected_note_as_versioned_proposal_only():
    result = await workflow().run(
        request(
            "安排3天复习计划，并整理到这份笔记",
            document={
                "id": "note-one",
                "version": 4,
                "title": "已有笔记",
                "content": "原始内容",
            },
        )
    )
    proposal = result["documentProposal"]
    assert proposal["operation"] == "update"
    assert proposal["documentId"] == "note-one"
    assert proposal["baseVersion"] == 4
    assert proposal["content"].startswith("原始内容\n\n# 复习计划")
    assert "确认保存" in result["answer"]


@pytest.mark.asyncio
async def test_user_time_is_retained_without_inventing_more_hours():
    result = await workflow().run(request("安排3天复习计划，每天2小时"))
    assert "每天2小时" in result["studyPlan"]["basis"][1]
    assert "未提供" not in result["studyPlan"]["basis"][1]


def test_compound_school_preferences_keep_explicit_region_constraints():
    plan = local_orchestration(
        request("安排复习计划，并且只推荐北京的2027年081200学硕院校")
    )
    assert plan.conditionPatch.regions == ["北京"]
    assert plan.conditionPatch.regionConstraint == "required"
    assert plan.conditionPatch.examYear == 2027
    assert plan.conditionPatch.majorCodes == ["081200"]


def test_framework_import_disables_implicit_environment_loading_in_fresh_process():
    script = """
import os
import dotenv
original = dotenv.load_dotenv
calls = []
def checked(*args, **kwargs):
    assert os.environ.get("PYTHON_DOTENV_DISABLED") == "1"
    calls.append(True)
    return original(*args, **kwargs)
dotenv.load_dotenv = checked
from core.framework import Agent
assert calls
assert os.environ.get("PYTHON_DOTENV_DISABLED") == "test-previous"
"""
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHON_DOTENV_DISABLED": "test-previous"},
    )


@pytest.mark.asyncio
async def test_failed_optional_school_expert_retains_study_result(monkeypatch):
    flow = workflow()

    async def fail(_):
        raise ToolUnavailable("synthetic_failure")

    monkeypatch.setattr(flow.engine, "schools", fail)
    result = await flow.run(request("安排3天复习计划，并推荐院校"))
    assert result["outcome"] == "COMPLETED"
    assert len(result["studyPlan"]["days"]) == 3
    assert "SCHOOL：暂时不可用" in result["notice"]
    assert "candidates" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["你好", "我暂时跳过诊断，请介绍可以使用的功能"])
async def test_basic_dialogue_needs_no_external_model(text):
    flow = workflow(enabled=True)
    result = await flow.run(request(text))
    assert result["outcome"] == "COMPLETED"
    assert "考研" in result["answer"] or "408" in result["answer"]
    flow.engine.model.generate.assert_not_awaited()


@pytest.mark.parametrize(
    "steps",
    [
        [{"agent": "TERMINAL", "dependsOn": []}],
        [{"agent": "LEARNING", "dependsOn": ["LEARNING"]}],
        [
            {"agent": "SCHOOL", "dependsOn": ["LEARNING"]},
            {"agent": "LEARNING", "dependsOn": []},
        ],
        [
            {"agent": "LEARNING", "dependsOn": []},
            {"agent": "LEARNING", "dependsOn": []},
        ],
        [{"agent": "SCHOOL", "dependsOn": [], "ownerId": 2}],
    ],
)
def test_invalid_expert_graphs_are_rejected(steps):
    with pytest.raises(ValidationError):
        ConversationResolution(
            action="MULTI_AGENT", standaloneQuery="test", planVersion=2, steps=steps
        )


def test_registered_tools_reject_unknown_names_parameters_and_duplicates():
    tool = ValidatedTool(
        "read", "synthetic read", EmptyParameters, lambda: {"ok": True}
    )
    registry = StrictToolRegistry()
    registry.register_tool(tool)
    assert json.loads(registry.execute_tool("read", "{}")) == {"ok": True}
    with pytest.raises(ValueError, match="duplicate"):
        registry.register_tool(tool)
    with pytest.raises(ValueError, match="unknown"):
        registry.execute_tool("terminal", "{}")
    with pytest.raises(ValidationError):
        registry.execute_tool("read", '{"userId":2}')


def test_context_rejects_indivisible_document_without_tokenizer_network(monkeypatch):
    import tiktoken

    monkeypatch.setattr(
        tiktoken,
        "get_encoding",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("unexpected tokenizer access")
        ),
    )
    payload = {
        "input": "线程",
        "document": {"content": "资料" * 20000},
        "sources": [{"id": "s", "version": "v1"}],
    }
    from core.errors import ModelUnavailable

    with pytest.raises(ModelUnavailable, match="context_budget_exceeded"):
        AuthorizedContextBuilder().messages("system", payload)
    assert len(payload["document"]["content"]) == 40000


@pytest.mark.asyncio
async def test_sync_stream_requires_async_entry_without_printing_private_messages(
    capsys,
):
    async with AsyncOpenAI(api_key="synthetic-key", max_retries=0) as client:
        model = AsyncHelloAgentsLLM(
            client,
            model="fixture",
            api_key="synthetic-key",
            base_url="https://provider.test",
        )
        with pytest.raises(RuntimeError, match="use_astream_invoke"):
            model.stream_invoke([{"role": "user", "content": "PRIVATE-SYNC-CONTEXT"}])
    output = capsys.readouterr()
    assert output.out == ""
    assert "PRIVATE-SYNC-CONTEXT" not in output.err


@pytest.mark.asyncio
async def test_specialist_histories_do_not_mix_between_concurrent_requests():
    flow = workflow()
    one, two = await asyncio.gather(
        flow.run(
            request(
                "安排3天复习计划",
                learningContext={
                    "statistics": {"knowledgePoints": [{"knowledgePoint": "A-only"}]}
                },
            )
        ),
        flow.run(
            request(
                "安排2天复习计划",
                userId=2,
                learningContext={
                    "statistics": {"knowledgePoints": [{"knowledgePoint": "B-only"}]}
                },
            )
        ),
    )
    assert "B-only" not in json.dumps(one)
    assert "A-only" not in json.dumps(two)


@pytest.mark.asyncio
async def test_cancellation_releases_all_experts_and_native_history(monkeypatch):
    started, released = asyncio.Event(), asyncio.Event()

    async def wait(self, state):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            released.set()

    monkeypatch.setattr(LearningAgent, "handle", wait)
    flow = workflow()
    coordinator = ConversationCoordinator(flow.engine)
    task = asyncio.create_task(coordinator.execute(request("安排3天复习计划")))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert released.is_set()
    assert coordinator.get_history() == []


@pytest.mark.asyncio
async def test_cancelling_provider_stream_closes_transport_and_stops_deltas():
    started, closed = asyncio.Event(), asyncio.Event()

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            body = {
                "id": "x",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "fixture",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": '{"answer":"first'},
                        "finish_reason": None,
                    }
                ],
            }
            yield ("data: " + json.dumps(body) + "\n\n").encode()
            await asyncio.Event().wait()

        async def aclose(self):
            closed.set()

    config = Settings(
        _env_file=None,
        AGENT_INTERNAL_KEY=KEY,
        LLM_ENABLED=True,
        LLM_API_KEY="synthetic",
    )
    model = ModelClient(config)
    model.client = AsyncOpenAI(
        api_key="synthetic",
        max_retries=0,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(
                    200,
                    headers={"content-type": "text/event-stream"},
                    stream=SlowStream(),
                )
            )
        ),
    )
    events = []

    async def sink(event):
        events.append(event)
        started.set()

    token = stream_sink.set(sink)
    task = asyncio.create_task(model.generate("test", {}, Answer))
    try:
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert closed.is_set()
        assert len(events) == 1
    finally:
        stream_sink.reset(token)
        await model.close()


@pytest.mark.asyncio
async def test_parallel_phase_budget_does_not_consume_global_allowance_when_rejected():
    global_budget, phase = CallBudget(4, 1), CallBudget(2)
    token, phase_token = execution_budget.set(global_budget), phase_budget.set(phase)
    config = Settings(
        _env_file=None,
        AGENT_INTERNAL_KEY=KEY,
        LLM_ENABLED=True,
        LLM_API_KEY="synthetic",
    )
    calls = []

    def provider(req):
        calls.append(1)
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "x",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": '{"answer":"x","sourceIds":["s"]}',
                        },
                    }
                ],
            },
        )

    model = ModelClient(config)
    model.client = AsyncOpenAI(
        api_key="synthetic",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(provider)),
    )
    try:
        results = await asyncio.gather(
            *(model.generate("test", {}, Answer) for _ in range(5)),
            return_exceptions=True,
        )
        assert len(calls) == 2 and global_budget.used == 3 and phase.used == 2
        assert sum(isinstance(value, RuntimeError) for value in results) == 3
    finally:
        execution_budget.reset(token)
        phase_budget.reset(phase_token)
        await model.close()


def test_plan_and_stream_share_four_attempt_budget_through_java_checkpoint():
    calls = []

    def provider(req):
        body = json.loads(req.content)
        calls.append(body)
        payload = json.loads(body["messages"][1]["content"])
        if body["model"] == "router":
            value = {
                "action": "MULTI_AGENT",
                "standaloneQuery": "进程与线程",
                "planVersion": 2,
                "steps": [
                    {"agent": "KNOWLEDGE", "dependsOn": []},
                    {"agent": "SCHOOL", "dependsOn": []},
                ],
            }
        elif "candidates" in payload:
            value = {
                "explanations": [
                    {
                        "programId": item["programId"],
                        "text": next(
                            source["content"]
                            for source in payload["sources"]
                            if source["id"] in item["sourceIds"]
                        ),
                        "sourceIds": item["sourceIds"],
                    }
                    for item in payload["candidates"]
                ]
            }
        else:
            value = {
                "answer": "线程共享地址空间，保留各自的栈。",
                "sourceIds": ["os-threads#0"],
            }
        if body.get("stream"):
            from tests.chat_wire_app import ProviderStream

            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=ProviderStream([json.dumps(value, ensure_ascii=False)], 0),
            )
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "x",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(value, ensure_ascii=False),
                        },
                    }
                ],
            },
        )

    config = Settings(
        _env_file=None,
        AGENT_INTERNAL_KEY=KEY,
        LLM_ENABLED=True,
        LLM_API_KEY="synthetic",
        LLM_MODEL_ROUTER="router",
        LLM_MODEL_MAIN="main",
    )
    model = ModelClient(config)
    model.client = AsyncOpenAI(
        api_key="synthetic",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(provider)),
    )
    body = request(
        "解释进程与线程，并比较这些条件",
        privacy={
            "modelAllowed": True,
            "scopes": ["profile"],
            "provider": config.LLM_BASE_URL,
        },
        conditions={
            "examYear": 2027,
            "majorCodes": ["081200"],
            "degreeType": "academic",
        },
    ).model_dump()
    with TestClient(create_app(config, model=model)) as client:
        plan = client.post(
            "/internal/rag/conversation/plan",
            headers={"X-Internal-Key": KEY},
            json=body,
        ).json()
        assert plan["modelCallsUsed"] == 1
        response = client.post(
            "/internal/rag/conversation/stream",
            headers={"X-Internal-Key": KEY},
            json={**body, "preparedPlan": plan},
        )
        events = [
            json.loads(line[6:])
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        assert events[-1]["type"] == "result"
        assert len(events[-1]["response"]["result"]["candidates"]) == 3
        assert len(calls) == 4
