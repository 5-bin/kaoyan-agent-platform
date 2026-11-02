"""The main chat and PR compatibility endpoint use one native knowledge expert."""

import json

import pytest

from agents.knowledge import KnowledgeAgent
from core.framework import Agent
from core.streaming import partial_json, project
from schemas import TutorExplanation
from tests.test_tutor import tutor
from tests.test_workflows import HEADERS, FakeModel, client


def events(response):
    return [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


@pytest.mark.parametrize("enabled", [False, True])
def test_main_tutor_uses_same_native_expert_without_parser_attempt(
    enabled, monkeypatch
):
    assert issubclass(KnowledgeAgent, Agent)
    entered = []
    original = KnowledgeAgent.tutor

    async def capture(self, req):
        entered.append(req.attempt.recordId)
        return await original(self, req)

    monkeypatch.setattr(KnowledgeAgent, "tutor", capture)
    model = FakeModel(
        TutorExplanation(explanation="按已保存版本核对你的选择。", standardAnswer="B")
    )
    body = tutor()
    body["taskType"] = "CHAT"
    with client(model, enabled=enabled) as c:
        plan = c.post("/internal/rag/conversation/plan", headers=HEADERS, json=body)
        assert plan.status_code == 200
        assert plan.json()["action"] == "WRONG_QUESTION_TUTOR"
        assert plan.json()["modelCallsUsed"] == 0
        assert model.calls == 0
        body["preparedPlan"] = plan.json()
        response = c.post(
            "/internal/rag/conversation/stream", headers=HEADERS, json=body
        )
    result = next(
        row["response"] for row in events(response) if row["type"] == "result"
    )
    assert result["status"] == "SUCCESS"
    assert result["result"]["standardAnswer"] == "B"
    assert result["result"]["recordId"] == 7
    assert entered == [7]
    assert model.calls == int(enabled)


def test_tutor_explanation_projects_to_existing_answer_slot_across_escaped_chunks():
    assert project(partial_json('{"explanation":"中\\u6587'))["answer"] == "中文"
    assert (
        project(partial_json('{"explanation":"中文\\n后续"'))["answer"] == "中文\n后续"
    )


def test_compound_tutor_and_study_plan_keep_attempt_inside_knowledge_expert(
    monkeypatch,
):
    from agents.learning import LearningAgent

    original = LearningAgent.handle
    seen = []

    async def inspect(self, state):
        seen.append(state[0].attempt)
        return await original(self, state)

    monkeypatch.setattr(LearningAgent, "handle", inspect)
    body = tutor()
    body.update(taskType="CHAT", userInput="解释这次错题，并安排3天复习计划")
    model = FakeModel(error=True)
    with client(model) as c:
        planned = c.post("/internal/rag/conversation/plan", headers=HEADERS, json=body)
        assert planned.status_code == 200
        assert [step["agent"] for step in planned.json()["steps"]] == [
            "LEARNING",
            "STUDY_PLAN",
            "KNOWLEDGE",
        ]
        body["preparedPlan"] = planned.json()
        response = c.post(
            "/internal/rag/conversation/stream", headers=HEADERS, json=body
        )
    result = next(
        row["response"]["result"] for row in events(response) if row["type"] == "result"
    )
    assert len(result["studyPlan"]["days"]) == 3
    assert result["standardAnswer"] == "B"
    assert result["recordId"] == 7
    assert seen == [None]
    assert model.calls == 0
