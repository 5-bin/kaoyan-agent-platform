"""Audit regressions: preserved intents, explicit failures and deterministic budgets."""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from pydantic import ValidationError

from agents.coordinator import ConversationCoordinator
from agents.learning import LearningAgent
from agents.note import NoteAgent
from agents.practice import PracticeAgent
from agents.results import StepContext, contribute
from agents.study import StudyPlannerAgent
from config import Settings
from core.errors import InvalidModelOutput, ModelUnavailable
from core.model import ModelClient
from core.runtime import CallBudget, execution_budget
from intents import ConditionExtractor
from main import create_app
from tests.test_conversation import KEY, workflow
from tests.test_multiagent import request
from tools.registry import InstructionParameters

CONSENT = {
    "modelAllowed": True,
    "scopes": ["stats", "profile", "document"],
    "provider": "https://open.bigmodel.cn/api/paas/v4",
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,expected",
    [
        ("解释TCP拥塞控制，并推荐专业", ["KNOWLEDGE", "SCHOOL"]),
        ("分析错题并推荐专业", ["LEARNING", "SCHOOL"]),
        ("分析薄弱点，安排3天复习，并推荐院校", ["LEARNING", "STUDY_PLAN", "SCHOOL"]),
        ("不要推荐院校，解释TCP拥塞控制", []),
    ],
)
async def test_route_matrix_keeps_each_positive_intent(text, expected):
    flow = workflow()
    plans = [await flow.plan(request(text)) for _ in range(3)]
    assert all([step.agent for step in plan.steps] == expected for plan in plans)
    if not expected:
        assert plans[0].action == "KNOWLEDGE_QA"


@pytest.mark.asyncio
async def test_practice_and_note_ambiguity_prevents_reads_and_writes():
    flow = workflow(enabled=True)
    req = request("生成5道关于二叉树的练习，并整理成笔记", privacy=CONSENT)
    plan = await flow.plan(req)
    assert plan.operation == "NONE" and plan.reads == [] and not plan.steps
    result = await flow.run(req)
    assert result["outcome"] == "NEEDS_INPUT"
    assert "练习和笔记" in result["answer"] and "documentProposal" not in result
    flow.engine.model.generate.assert_not_awaited()


def test_shared_condition_extractor_preserves_unset_and_rejects_conflicts():
    patch = ConditionExtractor.extract("只推荐北京2027年081200学硕专业").model_dump(
        exclude_unset=True
    )
    assert patch == {
        "examYear": 2027,
        "majorCodes": ["081200"],
        "degreeType": "academic",
        "regions": ["北京"],
        "regionConstraint": "required",
    }
    assert ConditionExtractor.extract("解释TCP").model_dump(exclude_unset=True) == {}
    assert ConditionExtractor.conflicting("2026与2027年")
    assert ConditionExtractor.conflicting("学硕和专硕")


@pytest.mark.parametrize("text", [
    "页面大小为2048字节，逻辑地址的页内偏移需要几位",
    "主存地址100000对应哪个Cache组",
    "TCP拥塞控制中阈值为2048时窗口如何变化",
])
def test_bare_numbers_in_questions_are_not_admission_conditions(text):
    assert ConditionExtractor.extract(text).model_dump(exclude_unset=True) == {}
    assert not ConditionExtractor.conflicting(text + "，若为2049呢")


def test_condition_only_followups_still_set_year_and_major():
    assert ConditionExtractor.extract("2027").model_dump(exclude_unset=True) == {"examYear": 2027}
    assert ConditionExtractor.extract("081200").model_dump(exclude_unset=True) == {"majorCodes": ["081200"]}
    assert ConditionExtractor.extract("择校2027").model_dump(exclude_unset=True) == {"examYear": 2027}


@pytest.mark.asyncio
async def test_numeric_knowledge_question_keeps_session_conditions():
    flow = workflow()
    req = request(
        "页面大小为2048字节，逻辑地址的页内偏移需要几位",
        conditions={"examYear": 2027, "majorCodes": ["081200"]},
    )
    plan = await flow.plan(req)
    assert plan.action != "SCHOOL_RECOMMEND"
    assert plan.conditionPatch.model_dump(exclude_unset=True) == {}
    result = await flow.run(req)
    assert result["conditions"]["examYear"] == 2027
    assert result["conditions"]["majorCodes"] == ["081200"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [ModelUnavailable("synthetic"), TimeoutError(), InvalidModelOutput("synthetic"), ModelUnavailable("context_budget_exceeded")],
)
async def test_note_expected_failure_has_no_placeholder(failure):
    flow = workflow(enabled=True)
    flow.engine.model.generate.side_effect = failure
    result = await flow.run(request("创建一份线程笔记", privacy=CONSENT))
    assert (
        result["outcome"] == "UNSUPPORTED" and result["explanationMode"] == "fallback"
    )
    assert "documentProposal" not in result and result["notice"]
    if failure.args == ("context_budget_exceeded",):
        assert "输入预算" in result["answer"] and "未发送模型请求" in result["notice"]


@pytest.mark.asyncio
async def test_compound_note_failure_keeps_other_expert_results():
    flow = workflow(enabled=True)
    flow.engine.model.generate.side_effect = TimeoutError()
    result = await flow.run(
        request(
            "创建一份笔记并推荐院校",
            privacy=CONSENT,
            conditions={
                "examYear": 2027,
                "majorCodes": ["081200"],
                "degreeType": "academic",
            },
        )
    )
    assert result["outcome"] == "COMPLETED" and result["partial"]
    assert result["candidates"] and "documentProposal" not in result
    assert [section["outcome"] for section in result["sections"]] == [
        "COMPLETED",
        "UNSUPPORTED",
    ]


@pytest.mark.parametrize("compound", [False, True])
def test_unknown_expert_bug_becomes_failed_http_result(monkeypatch, compound):
    async def bug(*args, **kwargs):
        raise TypeError("private-bug-body")

    monkeypatch.setattr(NoteAgent, "handle", bug)
    config = Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY)
    with TestClient(create_app(config)) as client:
        response = client.post(
            "/internal/rag/conversation/stream",
            headers={"X-Internal-Key": KEY},
            json=request(
                "创建一份笔记并推荐院校" if compound else "创建一份笔记"
            ).model_dump(),
        )
    assert '"type": "error"' in response.text
    assert (
        "private-bug-body" not in response.text
        and '"type": "result"' not in response.text
    )


@pytest.mark.asyncio
async def test_practice_has_its_own_operation_path_and_keeps_metadata(monkeypatch):
    async def unexpected(*args):
        raise AssertionError("LearningAgent must not process operations")

    monkeypatch.setattr(LearningAgent, "handle", unexpected)
    flow = workflow()
    req = request(
        "解释TCP，并安排5道练习",
        preparedPlan={
            "action": "MULTI_AGENT",
            "standaloneQuery": "解释TCP，并安排5道练习",
            "planVersion": 2,
            "steps": [
                {"agent": "KNOWLEDGE", "dependsOn": []},
                {"agent": "PRACTICE", "dependsOn": []},
            ],
            "operation": "PRACTICE_CREATE",
            "target": "normal",
            "count": 5,
            "reads": ["questions"],
        },
        learningContext={
            "retrievalStatus": "READY",
            "total": 2,
            "readCount": 2,
            "items": [{"ref": "Q1", "scope": "questions", "answered": False}],
        },
    )
    result = await flow.run(req)
    assert result["operation"] == "PRACTICE_CREATE" and result["count"] == 5
    assert result["target"] == "normal" and result["total"] == result["readCount"] == 2
    assert result["references"] and result["partial"] is False
    flow.engine.model.generate.assert_not_awaited()
    assert not issubclass(PracticeAgent, LearningAgent)


@pytest.mark.asyncio
async def test_declared_study_dependency_is_required_but_not_implicitly_shared(
    monkeypatch,
):
    async def missing(self, state):
        return {"outcome": "COMPLETED", "answer": "synthetic"}

    monkeypatch.setattr(StudyPlannerAgent, "handle", missing)
    result = await workflow().run(request("安排3天复习计划并整理成笔记"))
    assert result["partial"] and "documentProposal" not in result
    assert result["sections"][-1]["outcome"] == "UNSUPPORTED"
    assert "上游复习计划缺失" in result["sections"][-1]["notice"]
    assert StepContext().study_plan is None


def test_merge_rejects_field_and_evidence_conflicts():
    with pytest.raises(ValueError, match="conflicting_expert_field"):
        contribute({"count": 1}, "PRACTICE", {"count": 2})
    with pytest.raises(ValueError, match="conflicting_expert_evidence"):
        contribute(
            {"evidence": [{"ref": "Q1", "version": "v1"}]},
            "PRACTICE",
            {"evidence": [{"ref": "Q1", "version": "v2"}]},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["conflict", "overflow"])
async def test_merge_never_silently_replaces_or_truncates_references(monkeypatch, mode):
    flow = workflow()
    reference = flow.engine.corpus.documents[0].reference().model_dump()

    async def result_for_step(self, req, plan, step, completed):
        refs = (
            [dict(reference, id="same", version=step.agent)]
            if mode == "conflict"
            else [dict(reference, id=f"{step.agent}-{index}") for index in range(11)]
        )
        return {
            "outcome": "COMPLETED",
            "answer": "synthetic",
            "explanationMode": "rules",
            "references": refs,
        }

    monkeypatch.setattr(ConversationCoordinator, "_execute_step", result_for_step)
    with pytest.raises(
        ValueError, match="conflicting_expert_reference|too_many_expert_references"
    ):
        await flow.run(request("解释TCP并推荐院校"))


def test_timeout_configuration_and_tool_instruction_bounds():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY, CONVERSATION_EXPERT_TIMEOUT=30)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY, AGENT_TASK_TIMEOUT=48)
    with pytest.raises(ValidationError):
        InstructionParameters(instruction="x" * 8001)


@pytest.mark.asyncio
async def test_three_experts_get_two_model_attempts_by_priority():
    for _ in range(3):
        flow = workflow(enabled=True)
        config = flow.engine.settings
        calls = []

        def provider(req):
            payload = json.loads(json.loads(req.content)["messages"][1]["content"])
            calls.append("STUDY_PLAN" if "days" in payload else "LEARNING")
            value = (
                {"days": [{"day": 1, "topic": "线程", "tasks": ["复习"]}], "basis": []}
                if "days" in payload
                else {"suggestions": [{"action": "COLLECT_SAMPLES"}]}
            )
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"content": json.dumps(value)},
                            "finish_reason": "stop",
                        }
                    ]
                },
            )

        model = ModelClient(config)
        model.client = AsyncOpenAI(
            api_key="synthetic",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(provider)),
        )
        flow.engine.model = model
        req = request(
            "顺序测试",
            privacy=CONSENT,
            preparedPlan={
                "action": "MULTI_AGENT",
                "standaloneQuery": "顺序测试",
                "planVersion": 2,
                "steps": [
                    {"agent": name, "dependsOn": []}
                    for name in ("STUDY_PLAN", "LEARNING", "NOTE")
                ],
                "reads": ["stats"],
                "studyDays": 1,
            },
            learningContext={"statistics": {"questionCount": 2, "correctCount": 1}},
        )
        budget = CallBudget(4)
        token = execution_budget.set(budget)
        try:
            result = await flow.run(req)
            assert calls == ["LEARNING", "STUDY_PLAN"]
            assert budget.used == 2
            assert [item["explanationMode"] for item in result["sections"]] == [
                "ai",
                "ai",
                "rules",
            ]
            assert result["partial"] and "documentProposal" not in result
        finally:
            execution_budget.reset(token)
            await model.close()


@pytest.mark.asyncio
async def test_stage_timeout_marks_all_unfinished_steps_and_releases_history(
    monkeypatch,
):
    released = asyncio.Event()

    async def slow(*args):
        try:
            await asyncio.Event().wait()
        finally:
            released.set()

    flow = workflow()
    flow.engine.settings.CONVERSATION_EXPERT_TIMEOUT = 0.02
    monkeypatch.setattr(StudyPlannerAgent, "handle", slow)
    coordinator = ConversationCoordinator(flow.engine)
    result = await coordinator.execute(request("安排3天复习计划并推荐院校"))
    assert released.is_set() and coordinator.get_history() == []
    assert result["partial"] and len(result["sections"]) == 3
    assert [item["outcome"] for item in result["sections"]] == [
        "COMPLETED",
        "UNSUPPORTED",
        "UNSUPPORTED",
    ]
