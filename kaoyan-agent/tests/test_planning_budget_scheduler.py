"""Offline P0 acceptance: intent, visible evidence, deadlines and request budgets."""

import asyncio
import copy
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from agents.resolver import PlanResolver, validate_plan
from config import Settings
from core.context import AuthorizedContextBuilder
from core.errors import InvalidModelOutput, ModelUnavailable
from core.model import ModelClient, generation_limits
from core.runtime import CallBudget, execution_budget, step_model_allowed, stream_sink
from core.scheduling import schedule_steps
from core.tokens import TokenCounter
from schemas import Answer, ConversationResolution, DocumentDraft, ExpertStep, StudyPlan
from tests.test_multiagent import request, workflow


@pytest.mark.asyncio
@pytest.mark.parametrize("text,action,steps,reads,operation,days", [
    ("分析我的学习情况", "LEARNING_ANALYSIS", [], ["stats"], "NONE", 7),
    ("查看正确率", "LEARNING_ANALYSIS", [], ["stats"], "NONE", 7),
    ("看看掌握情况", "LEARNING_ANALYSIS", [], ["stats"], "NONE", 7),
    ("分析练习记录", "LEARNING_ANALYSIS", [], ["practice"], "NONE", 7),
    ("分析我的学习情况，并推荐院校", "MULTI_AGENT", ["LEARNING", "SCHOOL"], ["stats"], "NONE", 7),
    ("分析一下我的学习情况，并安排 7 天复习", "STUDY_PLAN", ["LEARNING", "STUDY_PLAN"], ["stats"], "NONE", 7),
    ("安排三十天复习计划", "STUDY_PLAN", ["LEARNING", "STUDY_PLAN"], ["stats"], "NONE", 30),
    ("不要推荐院校，并解释TCP", "KNOWLEDGE_QA", [], [], "NONE", 7),
    ("不要生成笔记，分析学习情况", "LEARNING_ANALYSIS", [], ["stats"], "NONE", 7),
    ("不要推荐院校，并收藏 Q1", "LEARNING_ANALYSIS", [], ["favorite"], "FAVORITE_ADD", 7),
    ("不推荐院校，解释TCP", "KNOWLEDGE_QA", [], [], "NONE", 7),
    ("解释TCP，并创建一份笔记", "MULTI_AGENT", ["KNOWLEDGE", "NOTE"], [], "NONE", 7),
    ("收藏 Q1，并推荐院校", "MULTI_AGENT", ["SCHOOL", "PRACTICE"], ["favorite"], "FAVORITE_ADD", 7),
    ("取消收藏 Q1，并解释TCP", "MULTI_AGENT", ["KNOWLEDGE", "PRACTICE"], ["favorite"], "FAVORITE_REMOVE", 7),
    ("分析学习情况，并安排5道排序练习", "MULTI_AGENT", ["LEARNING", "PRACTICE"], ["questions", "stats"], "PRACTICE_CREATE", 7),
    ("收藏 Q1", "LEARNING_ANALYSIS", [], ["favorite"], "FAVORITE_ADD", 7),
    ("将错题本中的题加入收藏", "LEARNING_ANALYSIS", [], ["wrong"], "FAVORITE_ADD", 7),
    ("如何创建复习计划", "CHAT", [], [], "NONE", 7),
    ("例如安排7天复习并创建笔记", "CHAT", [], [], "NONE", 7),
])
async def test_golden_local_plans(text, action, steps, reads, operation, days):
    flow = workflow()
    plan = await flow.plan(request(text))
    assert (plan.action, [s.agent for s in plan.steps], plan.reads, plan.operation, plan.studyDays) == (action, steps, reads, operation, days)
    for step in plan.steps:
        assert step.dependsOn == (["LEARNING"] if "LEARNING" in steps and step.agent in {"SCHOOL", "STUDY_PLAN"} else [])
    flow.engine.model.generate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["安排0天复习", "安排31天复习", "安排100天复习", "安排7天或14天复习", "修改这份笔记"])
async def test_clarifications_are_inert(text):
    flow = workflow()
    plan = await flow.plan(request(text))
    assert plan.clarification and not plan.reads and not plan.steps and plan.operation == "NONE"
    flow.engine.model.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_compound_never_executes_only_one_requested_capability():
    flow = workflow()
    req = request("解释TCP，并推荐院校")
    result = await flow.engine.run(req)
    assert result["outcome"] == "NEEDS_INPUT" and "/tasks" in result["answer"]
    assert "candidates" not in result
    assert await PlanResolver(flow.engine).legacy(request("解释TCP"), allow_model=False) == "KNOWLEDGE_QA"
    flow.engine.model.generate.assert_not_awaited()


@pytest.mark.parametrize("fields", [
    {"action": "DOCUMENT_UPDATE"},
    {"action": "WRONG_QUESTION_TUTOR"},
    {"action": "CHAT", "reads": ["stats"], "clarification": "补充条件"},
    {"action": "CHAT", "operation": "FAVORITE_ADD", "reads": ["favorite"]},
    {"action": "LEARNING_ANALYSIS", "operation": "FAVORITE_ADD", "reads": ["wrong"], "target": "normal"},
    {"action": "MULTI_AGENT", "planVersion": 2, "steps": [{"agent": "LEARNING"}], "studyDays": 2},
    {"action": "STUDY_PLAN", "planVersion": 2, "steps": [{"agent": "LEARNING"}]},
])
def test_invalid_prepared_cross_fields_are_rejected(fields):
    plan = ConversationResolution(standaloneQuery="收藏 Q1", **fields)
    with pytest.raises(InvalidModelOutput):
        validate_plan(plan, request("收藏 Q1"))


def test_revalidation_keeps_unset_condition_patch_and_detects_mutated_graph():
    plan = ConversationResolution(action="SCHOOL_RECOMMEND", standaloneQuery="只考虑北京", conditionPatch={"regions": ["北京"]})
    assert validate_plan(plan, request("只考虑北京")).conditionPatch.model_dump(exclude_unset=True) == {"regions": ["北京"]}
    plan.steps = [ExpertStep(agent="SCHOOL", dependsOn=["SCHOOL"])]
    with pytest.raises(ValidationError):
        validate_plan(plan, request("只考虑北京"))


class UpperBoundCounter:
    mode = "test_utf8_upper_bound"

    def __init__(self):
        self.calls = 0

    def count(self, value):
        self.calls += 1
        return len(value.encode())


@pytest.mark.parametrize("word", ["review ", "复习资料"])
def test_context_trims_history_before_excerpt_and_preserves_metadata(word):
    payload = {"input": "复习TCP", "scope": ["stats"], "messages": [{"role": "user", "content": word * 500}],
               "references": [{"id": "r1", "version": "v3", "locator": "第1页", "content": word * 1000}]}
    original = copy.deepcopy(payload)
    prepared = AuthorizedContextBuilder(2000, UpperBoundCounter()).prepare("系统规则", payload)
    assert prepared.removed_history == 1 and prepared.shortened_excerpts == 1
    assert prepared.estimated_tokens <= 2000 and prepared.payload["scope"] == ["stats"]
    assert prepared.sources()["r1"]["version"] == "v3" and prepared.sources()["r1"]["locator"] == "第1页"
    assert prepared.messages[0]["content"] == "系统规则"
    assert payload == original


def test_large_statistics_reduce_rows_without_rewriting_totals_or_sample_flags():
    payload = {"input": "复习线程", "learningContext": {"statistics": {
        "questionCount": 999, "from": "2026-10-01", "to": "2026-10-30",
        "learningProfile": {"revision": 4, "sufficient": False, "assistedSamples": 8,
                            "groups": [{"knowledgePoint": f"线程{i}", "samples": 2, "sampleStatus": "INSUFFICIENT", "assisted": 1, "priority": i} for i in range(200)]}}}}
    original = copy.deepcopy(payload)
    counter = UpperBoundCounter()
    prepared = AuthorizedContextBuilder(4000, counter).prepare("规则", payload)
    stats = prepared.payload["learningContext"]["statistics"]
    assert prepared.removed_statistics > 0 and prepared.estimated_tokens <= 4000
    assert stats["questionCount"] == 999 and stats["learningProfile"]["sufficient"] is False
    assert stats["learningProfile"]["assistedSamples"] == 8
    assert all(row["sampleStatus"] == "INSUFFICIENT" and row["assisted"] == 1 for row in stats["learningProfile"]["groups"])
    assert payload == original
    assert counter.calls < 100  # Large profiles must not re-tokenize once per row.


@pytest.mark.parametrize("key", ["document", "attempt"])
def test_required_document_and_graded_snapshot_are_not_cut(key):
    with pytest.raises(ModelUnavailable, match="context_budget_exceeded"):
        AuthorizedContextBuilder(1000, UpperBoundCounter()).prepare("规则", {key: {"content": "必要原文" * 10000}})


def test_five_references_keep_versions_and_qualification_prose():
    refs = [{"id": str(i), "version": "v1", "content": "事实摘要" * 500} for i in range(5)]
    prepared = AuthorizedContextBuilder(3600, UpperBoundCounter()).prepare("规则", {"input": "事实", "references": refs})
    assert len(prepared.sources()) == 5 and all(row["version"] == "v1" for row in prepared.sources().values())
    with pytest.raises(ModelUnavailable):
        AuthorizedContextBuilder(1000, UpperBoundCounter()).prepare("规则", {"sources": [{"id": "s", "version": "v1", "content": "仅限符合资格条件的考生。" * 300}]})


def test_citation_cannot_use_a_removed_suffix_as_support():
    from grounding import verify
    original = "基础复习。" * 1000 + "量子纠缠依赖贝尔不等式实验验证。"
    prepared = AuthorizedContextBuilder(1500, UpperBoundCounter()).prepare("规则", {
        "references": [{"id": "s", "version": "v1", "content": original}]
    })
    claim = "量子纠缠依赖贝尔不等式实验验证。"
    assert claim not in prepared.sources()["s"]["content"]
    assert verify(claim, ["s"], prepared.sources())["status"] == "UNSUPPORTED"


def test_token_fallback_never_uses_network(monkeypatch):
    import core.tokens as module
    monkeypatch.setattr(module, "local_encoding", lambda: None)
    counter = TokenCounter()
    assert counter.mode == "utf8_piece_upper_bound" and counter.count("中文") == 6


@pytest.mark.asyncio
async def test_overflow_and_disabled_model_do_not_consume_attempts():
    flow = workflow(enabled=True)
    model = ModelClient(flow.engine.settings)
    factory = AsyncMock()
    model.client_factory = factory
    budget = CallBudget(4)
    token = execution_budget.set(budget)
    try:
        with pytest.raises(ModelUnavailable):
            await model.generate("规则", {"document": {"content": "文档" * 20000}}, DocumentDraft)
        model.settings.LLM_ENABLED = False
        with pytest.raises(ModelUnavailable):
            await model.generate("规则", {}, Answer)
        assert budget.used == model.budget.calls == 0
        factory.assert_not_called()
    finally:
        execution_budget.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_length_finish_reason_rejects_even_valid_json(streaming):
    def provider(req):
        value = '{"title":"笔记","content":"不完整"}'
        if streaming:
            data = "data: " + json.dumps({"choices": [{"index": 0, "delta": {"content": value}, "finish_reason": "length"}]}) + "\n\ndata: [DONE]\n\n"
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=data)
        return httpx.Response(200, json={"choices": [{"message": {"content": value}, "finish_reason": "length"}]})
    model = ModelClient(workflow(enabled=True).engine.settings)
    model.client = AsyncOpenAI(api_key="synthetic", max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    token = stream_sink.set(AsyncMock() if streaming else None)
    try:
        with pytest.raises(InvalidModelOutput, match="model_output_truncated"):
            await model.generate("规则", {}, DocumentDraft)
        assert model.budget.calls == 1
    finally:
        stream_sink.reset(token)
        await model.close()


def test_budget_configuration_and_thirty_day_output_allowance():
    settings = workflow().engine.settings
    assert generation_limits(settings, StudyPlan, {"days": 30}) == (12000, 8192)
    assert generation_limits(settings, DocumentDraft, {}) == (20000, 4096)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, AGENT_INTERNAL_KEY="synthetic-key-12345678", MODEL_CONTEXT_WINDOW=20000)


def done():
    return {"outcome": "COMPLETED", "answer": "完成", "explanationMode": "rules"}


@pytest.mark.asyncio
async def test_timeout_is_local_and_dependencies_skip_while_independent_step_runs():
    released = asyncio.Event()
    visited = []
    async def execute(step, completed):
        visited.append(step.agent)
        if step.agent == "LEARNING":
            try:
                await asyncio.Event().wait()
            finally:
                released.set()
        return done()
    steps = [ExpertStep(agent="LEARNING"), ExpertStep(agent="STUDY_PLAN", dependsOn=["LEARNING"]), ExpertStep(agent="SCHOOL")]
    result = await schedule_steps(steps, execute, lambda s: False, lambda s: False, CallBudget(2), .2, .01)
    assert result["LEARNING"]["outcome"] == result["STUDY_PLAN"]["outcome"] == "UNSUPPORTED"
    assert result["SCHOOL"]["outcome"] == "COMPLETED" and released.is_set()
    assert visited == ["LEARNING", "SCHOOL"]


@pytest.mark.asyncio
async def test_pure_rules_overlap_but_have_no_model_permission():
    first = asyncio.Event()
    second = asyncio.Event()
    async def execute(step, completed):
        assert not step_model_allowed.get()
        if step.agent == "PRACTICE":
            first.set()
            await second.wait()
        else:
            second.set()
            await first.wait()
        return done()
    steps = [ExpertStep(agent="PRACTICE"), ExpertStep(agent="NOTE")]
    result = await schedule_steps(steps, execute, lambda s: False, lambda s: True, CallBudget(2), 1, .5)
    assert all(row["outcome"] == "COMPLETED" for row in result.values())


@pytest.mark.asyncio
async def test_model_priority_and_unused_allowance_are_independent_of_plan_order():
    order, grants = [], []
    allowance = CallBudget(2)
    async def execute(step, completed):
        order.append(step.agent)
        if step_model_allowed.get():
            grants.append(step.agent)
            # LEARNING had insufficient evidence: its unused grant goes onward.
            if step.agent != "LEARNING":
                allowance.consume()
        return done()
    steps = [ExpertStep(agent=name) for name in ("NOTE", "KNOWLEDGE", "SCHOOL", "LEARNING")]
    await schedule_steps(steps, execute, lambda s: True, lambda s: False, allowance, 1, .5)
    assert order == ["LEARNING", "SCHOOL", "KNOWLEDGE", "NOTE"]
    assert grants == ["LEARNING", "SCHOOL", "KNOWLEDGE"] and allowance.used == 2


@pytest.mark.asyncio
async def test_cancellation_reclaims_every_parallel_child_and_resets_context():
    entered = asyncio.Event()
    finished = []
    async def execute(step, completed):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            finished.append(step.agent)
    task = asyncio.create_task(schedule_steps([ExpertStep(agent="PRACTICE"), ExpertStep(agent="NOTE")], execute,
                                             lambda s: False, lambda s: True, CallBudget(2), 1, .5))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert set(finished) == {"PRACTICE", "NOTE"} and step_model_allowed.get()


@pytest.mark.asyncio
async def test_compound_document_update_without_selection_is_inert():
    flow = workflow()
    plan = await flow.plan(request("推荐院校，并修改这份笔记"))
    assert plan.clarification and not plan.steps and not plan.reads and plan.operation == "NONE"
    flow.engine.model.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_study_note_does_not_append_to_selected_existing_document():
    req = request("安排3天复习，并创建一份笔记", document={"id": "selected", "version": 2, "title": "旧笔记", "content": "旧原文标记"})
    result = await workflow().run(req)
    proposal = result["documentProposal"]
    assert proposal["operation"] == "create" and proposal["documentId"] is None and proposal["baseVersion"] is None
    assert "旧原文标记" not in proposal["content"]


@pytest.mark.asyncio
async def test_parser_deadline_cancels_and_uses_local_fallback_once():
    flow = workflow(enabled=True)
    released = asyncio.Event()
    async def slow(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            released.set()
    flow.engine.model.generate.side_effect = slow
    flow.engine.settings.CONVERSATION_PARSE_TIMEOUT = .01
    plan = await flow.plan(request("解释TCP", privacy={"modelAllowed": True, "provider": flow.engine.settings.LLM_BASE_URL}))
    assert plan.action == "KNOWLEDGE_QA" and released.is_set()
    flow.engine.model.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_model_permissions_do_not_leak_between_concurrent_schedules():
    barrier = asyncio.Event()
    async def run_one(allow):
        async def execute(step, completed):
            if allow:
                barrier.set()
            await barrier.wait()
            await asyncio.sleep(0)
            assert step_model_allowed.get() is allow
            return done()
        return await schedule_steps([ExpertStep(agent="NOTE")], execute, lambda s: allow, lambda s: not allow, CallBudget(2), 1, .5)
    first, second = await asyncio.gather(run_one(True), run_one(False))
    assert first["NOTE"]["outcome"] == second["NOTE"]["outcome"] == "COMPLETED"
    assert step_model_allowed.get()


@pytest.mark.asyncio
async def test_transport_construction_failure_does_not_count_as_provider_request():
    model = ModelClient(workflow(enabled=True).engine.settings)
    def fail(**kwargs):
        raise RuntimeError("synthetic_factory_failure")
    model.client_factory = fail
    budget = CallBudget(2)
    token = execution_budget.set(budget)
    try:
        with pytest.raises(RuntimeError, match="synthetic_factory_failure"):
            await model.generate("规则", {}, Answer)
        assert budget.used == model.budget.calls == 0
    finally:
        execution_budget.reset(token)
