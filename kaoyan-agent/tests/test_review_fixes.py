"""Regressions for the 2026-11-02 agent review: routing, plans, privacy and degradation."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import agents.planning as planning
import core.admission_client as admission_client
from agents.coordinator import ANSWER_LIMIT, EXCERPT_MARK, ConversationCoordinator, merge_answers
from agents.results import ExpertResult
from config import Settings, provider_identifier
from conversation import ConversationWorkflow
from core.errors import ModelUnavailable
from intents import REGIONS, ConditionExtractor, positive_request
from learning import LearningAnswer
from main import create_app
from retrieval import Corpus, Retriever
from schemas import ChatRequest, CombinedAnswer, ConversationRequest, ConversationResolution, StudyPlan, Summary
from tests.test_conversation import workflow
from workflows import Workflows

KEY = "test-only-internal-key-123456"
HEADERS = {"X-Internal-Key": KEY}


class ScriptedModel:
    """Fails router parses and returns scripted outputs by schema; records payloads."""

    def __init__(self, outputs: dict, delay: float = 0) -> None:
        self.outputs, self.delay, self.payloads = outputs, delay, []

    async def generate(self, instruction, payload, schema, router=False):
        if self.delay:
            await asyncio.sleep(self.delay)
        if router or schema not in self.outputs:
            raise ModelUnavailable("not_scripted")
        self.payloads.append((schema, payload))
        value = self.outputs[schema]
        return value(payload) if callable(value) else value

    async def close(self):
        pass


def settings(**values):
    return Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY, **values)


def enabled_flow(model):
    config = settings(LLM_ENABLED=True, LLM_API_KEY="test-only")
    corpus = Corpus(config.RAG_DATA)
    return ConversationWorkflow(Workflows(config, corpus, Retriever(config, corpus), model)), config


def request(text, **values):
    return ConversationRequest.model_validate(
        {"taskId": "review", "userId": 1, "taskType": "CHAT", "userInput": text, **values}
    )


def consent(config, *scopes):
    return {"modelAllowed": True, "scopes": list(scopes), "provider": provider_identifier(config.LLM_BASE_URL)}


@pytest.mark.parametrize("text", ["进程和线程的区别", "TCP和UDP的区别", "栈和队列有什么区别", "分别解释TCP和UDP", "特别解释一下死锁"])
def test_words_containing_bie_are_not_negations(text):
    assert positive_request(text) == text


@pytest.mark.parametrize("text", ["别帮我推荐院校", "请别再推荐"])
def test_imperative_bie_still_negates(text):
    assert positive_request(text) == ""


@pytest.mark.asyncio
async def test_difference_questions_route_to_knowledge():
    flow = workflow()
    for text in ("进程和线程的区别", "TCP和UDP的区别"):
        assert (await flow.plan(request(text))).action == "KNOWLEDGE_QA"


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["解释2027年考研真题中的TCP拥塞控制", "2027年408真题TCP怎么考"])
async def test_knowledge_question_with_year_is_not_school_and_keeps_conditions(text):
    plan = await workflow().plan(request(text))
    assert plan.action == "KNOWLEDGE_QA"
    assert plan.conditionPatch.model_dump(exclude_unset=True) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("text,point", [("练习TCP", "TCP"), ("做几道TCP题", "TCP"), ("刷TCP题", "TCP"), ("练习红黑树", "红黑树")])
async def test_natural_practice_requests_create_practice(text, point):
    plan = await workflow().plan(request(text))
    assert (plan.action, plan.operation, plan.target, plan.knowledgePoint) == ("LEARNING_ANALYSIS", "PRACTICE_CREATE", "normal", point)
    assert plan.reads == ["questions"]


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["我的练习记录", "刷题功能是什么", "练习TCP和UDP"])
async def test_practice_lookalikes_do_not_create_practice(text):
    assert (await workflow().plan(request(text))).operation == "NONE"


def test_empty_session_conditions_keep_profile_year_and_preferences():
    flow = workflow()
    req = request("推荐院校", profile={"examYear": 2027}, preferences={"explainWithAi": False, "degreeType": "academic"})
    ConversationCoordinator(flow.engine).base(req, ConversationResolution(action="SCHOOL_RECOMMEND", standaloneQuery="推荐院校"))
    assert req.profile.examYear == 2027
    assert req.preferences.explainWithAi is False and req.preferences.degreeType == "academic"


@pytest.mark.asyncio
async def test_legacy_session_school_request_does_not_ask_for_known_year():
    result = await workflow().run(request("推荐院校", profile={"examYear": 2027, "targetMajor": "081200"}))
    assert "请在个人档案填写报考年份" not in result.get("followUp", [])


@pytest.mark.parametrize("text", ["使用这些题创建练习", "用选中的题出一套练习"])
def test_visible_practice_without_snapshot_clarifies_instead_of_503(text):
    with TestClient(create_app(settings())) as client:
        response = client.post("/internal/rag/conversation/plan", headers=HEADERS,
                               json={"taskId": "review", "userId": 1, "taskType": "CHAT", "userInput": text})
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["clarification"] and plan["operation"] == "NONE" and plan["reads"] == []


def test_all_provinces_is_no_region_constraint():
    text = "推荐2027年学硕，" + "、".join(REGIONS)
    assert "regions" not in ConditionExtractor.extract(text).model_dump(exclude_unset=True)
    with TestClient(create_app(settings())) as client:
        response = client.post("/internal/rag/conversation/plan", headers=HEADERS,
                               json={"taskId": "review", "userId": 1, "taskType": "CHAT", "userInput": text})
    assert response.status_code == 200, response.text


def test_plan_parser_timeout_reaches_local_fallback():
    config = settings(LLM_ENABLED=True, LLM_API_KEY="test-only", CONVERSATION_PARSE_TIMEOUT=0.05)
    model = ScriptedModel({}, delay=1)
    with TestClient(create_app(config, model=model)) as client:
        response = client.post("/internal/rag/conversation/plan", headers=HEADERS, json={
            "taskId": "review", "userId": 1, "taskType": "CHAT", "userInput": "一个无法本地分类的新话题",
            "privacy": consent(config)})
    assert response.status_code == 200, response.text
    assert response.json()["action"] == "CHAT"


def practice_summary(config, scopes, summary):
    questions = [{"id": i, "subject": "操作系统", "knowledgePoint": "死锁", "content": f"题{i}",
                  "answer": "A", "correct": i % 2 == 0} for i in range(1, 5)]
    return ChatRequest.model_validate({"taskId": "review", "userId": 1, "taskType": "PRACTICE_SUMMARY",
                                       "sessionId": "s1", "questions": questions, "privacy": consent(config, *scopes)})


@pytest.mark.asyncio
async def test_wrong_scope_summary_sends_only_wrong_attempts():
    model = ScriptedModel({Summary: Summary(summary="复习死锁的必要条件。")})
    flow, config = enabled_flow(model)
    result = await flow.engine.run(practice_summary(config, ["wrong"], None))
    payload = model.payloads[0][1]
    assert payload["statistics"] == {}
    assert [q["correct"] for q in payload["questions"]] == [False, False]
    assert result["explanationMode"] == "ai"


@pytest.mark.asyncio
async def test_summary_cannot_change_rule_numbers():
    model = ScriptedModel({Summary: Summary(summary="本批次正确率100%，答对4题。")})
    flow, config = enabled_flow(model)
    result = await flow.engine.run(practice_summary(config, ["wrong", "stats"], None))
    assert result["explanationMode"] == "fallback"
    assert result["answer"] == "有效作答4题，正确2题。"


@pytest.mark.asyncio
async def test_compound_summary_cannot_invent_numbers_without_references():
    model = ScriptedModel({
        LearningAnswer: LearningAnswer(suggestions=[{"action": "PRACTICE_RELATED"}]),
        StudyPlan: lambda payload: StudyPlan(days=[{"day": d, "topic": "复习", "tasks": ["做题"]} for d in range(1, payload["days"] + 1)]),
        CombinedAnswer: CombinedAnswer(answer="你已完成1000道题，正确率98%。"),
    })
    flow, config = enabled_flow(model)
    context = {"statistics": {"questionCount": 12, "correctCount": 5,
                              "knowledgePoints": [{"knowledgePoint": "未登记主题甲乙丙", "questionCount": 12}]}}
    text = "分析我的学情并制定3天复习计划"
    plan = await flow.plan(request(text, privacy=consent(config, "stats")))
    result = await flow.run(request(text, privacy=consent(config, "stats"),
                                    preparedPlan=plan.model_dump(by_alias=True), learningContext=context))
    assert "1000" not in result["answer"]
    assert CombinedAnswer not in [schema for schema, _ in model.payloads]


@pytest.mark.asyncio
async def test_learning_answer_cannot_invent_numbers():
    model = ScriptedModel({LearningAnswer: LearningAnswer(answer="你的正确率为98%。")})
    flow, config = enabled_flow(model)
    context = {"statistics": {"questionCount": 12, "correctCount": 5}}
    plan = await flow.plan(request("分析我的学情", privacy=consent(config, "stats")))
    result = await flow.run(request("分析我的学情", privacy=consent(config, "stats"),
                                    preparedPlan=plan.model_dump(by_alias=True), learningContext=context))
    assert result["explanationMode"] == "fallback" and "98" not in result["answer"]


def test_hybrid_survives_qdrant_client_errors():
    from qdrant_client.http.exceptions import ResponseHandlingException

    config = settings(RAG_BACKEND="hybrid")
    retriever = Retriever(config, Corpus(config.RAG_DATA))

    class Broken:
        def search(self, *args, **kwargs):
            raise ResponseHandlingException(ConnectionError("refused"))

        def close(self):
            pass

    retriever.vector = Broken()
    results = retriever.search("TCP 重传", "knowledge", 5)
    assert results and results[0].id.startswith("cn-tcp")


def test_merged_answers_fit_contract_and_mark_excerpts():
    answer, shortened = merge_answers([("学情分析", "甲" * 12000), ("知识辅导", "乙" * 12000), ("复习安排", "短")])
    assert shortened and len(answer) <= ANSWER_LIMIT
    assert answer.count(EXCERPT_MARK) == 2 and "复习安排\n短" in answer
    ExpertResult.model_validate({"outcome": "COMPLETED", "answer": answer, "explanationMode": "rules",
                                 "references": [], "resolvedTaskType": "CHAT", "releaseId": "r"})
    assert merge_answers([("a", "x"), ("b", "y")]) == ("a\nx\n\nb\ny", False)


def test_broken_admission_registry_does_not_stop_the_agent(monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("ADMISSION_SOURCES_INVALID")

    monkeypatch.setattr(admission_client, "AdmissionLinksRegistry", broken)
    monkeypatch.setattr(planning, "load_sources", broken)
    with TestClient(create_app(settings(ADMISSION_MCP_ENABLED=True))) as client:
        health = client.get("/health").json()
        response = client.post("/internal/rag/conversation/plan", headers=HEADERS, json={
            "taskId": "review", "userId": 1, "taskType": "CHAT", "userInput": "查官网南京审计大学"})
    assert health["mcpTools"]["admission"] == {"enabled": True, "state": "UNAVAILABLE", "errorCode": "START_FAILED"}
    assert response.status_code == 200, response.text
    assert response.json()["clarification"] == planning.REGISTRY_UNAVAILABLE


def test_tool_registration_is_silent(capsys):
    from tools.registry import EmptyParameters, StrictToolRegistry, ValidatedTool

    registry = StrictToolRegistry()
    registry.add(ValidatedTool("silent_tool", "测试工具", EmptyParameters, lambda: None))
    assert registry.get_tool("silent_tool") is not None
    assert capsys.readouterr().out == ""
    with pytest.raises(ValueError, match="duplicate_tool"):
        registry.add(ValidatedTool("silent_tool", "测试工具", EmptyParameters, lambda: None))


@pytest.mark.parametrize("text,expected", [
    ("只考虑江苏", "required"),
    ("地区限定为上海", "required"),
    ("不只考虑江苏，浙江也可以", "preferred"),
    ("只考学硕，北京优先", "preferred"),
])
def test_region_constraint_follows_the_region_phrase(text, expected):
    assert ConditionExtractor.extract(text).regionConstraint == expected


def test_vector_encoder_uses_project_embedding_cache(monkeypatch, tmp_path):
    import retrieval

    seen = {}

    class Recorder:
        def __init__(self, model, cache_dir=None, threads=None, local_files_only=False):
            seen.update(cache_dir=cache_dir, local_files_only=local_files_only)

        def encode(self, texts):
            return [[0.0] for _ in texts]

    monkeypatch.setattr(retrieval, "FastEmbedEncoder", Recorder)
    config = settings(RAG_INDEX=tmp_path, QUESTION_MODEL_CACHE=tmp_path / "embedding")
    index = retrieval.VectorIndex(config, Corpus(config.RAG_DATA), client=object())
    index.encode(["x"])
    assert seen["cache_dir"] == str(tmp_path / "embedding")


def test_parse_timeout_must_leave_java_room_for_fallback():
    with pytest.raises(ValueError, match="INVALID_PLAN_TIMEOUT"):
        settings(CONVERSATION_PARSE_TIMEOUT=20, CONVERSATION_EXPERT_TIMEOUT=12, CONVERSATION_SUMMARY_TIMEOUT=10)
    assert settings(CONVERSATION_PARSE_TIMEOUT=19, CONVERSATION_EXPERT_TIMEOUT=13).CONVERSATION_PARSE_TIMEOUT == 19


LONG_STATS = {"statistics": {"questionCount": 900, "correctCount": 500, "from": "2026-01-01", "to": "2026-10-31",
                             "knowledgePoints": [{"knowledgePoint": f"合成知识点{i:03d}" + "细分主题" * 12, "questionCount": 3}
                                                 for i in range(366)]}}


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["分析我的学情", "分析我的学情并制定3天复习计划"])
async def test_long_rule_learning_answers_stay_within_the_result_limit(text):
    flow = workflow()
    privacy = {"modelAllowed": False, "scopes": ["stats"]}
    plan = await flow.plan(request(text, privacy=privacy))
    result = await flow.run(request(text, privacy=privacy, preparedPlan=plan.model_dump(by_alias=True), learningContext=LONG_STATS))
    assert result["outcome"] == "COMPLETED"
    assert len(result["answer"]) <= ANSWER_LIMIT
    assert "未在文字中展示" in result["answer"]


@pytest.mark.asyncio
async def test_practice_summary_accepts_provider_extra_fields():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from openai.types.chat import ChatCompletion

    from core.model import ModelClient

    config = settings(LLM_ENABLED=True, LLM_API_KEY="test-only")
    content = json.dumps({"summary": "复习死锁的必要条件。", "additional": "模型附加内容"}, ensure_ascii=False)
    response = ChatCompletion.model_validate({"id": "t", "object": "chat.completion", "created": 0, "model": "t",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}]})
    model = ModelClient(config)
    model.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=response))))
    corpus = Corpus(config.RAG_DATA)
    engine = Workflows(config, corpus, Retriever(config, corpus), model)
    result = await engine.run(practice_summary(config, ["wrong", "stats"], None))
    assert result["explanationMode"] == "ai"
    assert result["answer"] == "复习死锁的必要条件。"
    assert "additional" not in json.dumps(result, ensure_ascii=False)


def compound_model(summary_text):
    return ScriptedModel({
        LearningAnswer: LearningAnswer(suggestions=[{"action": "PRACTICE_RELATED"}]),
        StudyPlan: lambda payload: StudyPlan(days=[{"day": d, "topic": "死锁", "tasks": ["复习死锁的必要条件"]}
                                                   for d in range(1, payload["days"] + 1)]),
        CombinedAnswer: CombinedAnswer(answer=summary_text),
    })


async def run_compound(model):
    flow, config = enabled_flow(model)
    context = {"statistics": {"questionCount": 12, "correctCount": 5,
                              "knowledgePoints": [{"knowledgePoint": "死锁", "questionCount": 6},
                                                  {"knowledgePoint": "TCP拥塞控制", "questionCount": 6}]}}
    text = "分析我的学情并制定3天复习计划"
    plan = await flow.plan(request(text, privacy=consent(config, "stats")))
    return await flow.run(request(text, privacy=consent(config, "stats"),
                                  preparedPlan=plan.model_dump(by_alias=True), learningContext=context))


@pytest.mark.asyncio
async def test_compound_learning_facts_are_joined_without_model_rewriting():
    model = compound_model("不应调用的综合解释")
    result = await run_compound(model)
    assert result["explanationMode"] == "rules"
    assert "有效作答12次，正确5次" in result["answer"]
    assert "已安排3天" in result["answer"]
    assert CombinedAnswer not in [schema for schema, _ in model.payloads]


@pytest.mark.asyncio
async def test_compound_summary_with_unsupported_additions_is_rejected():
    model = compound_model("建议你放弃计算机方向并改报金融学硕士，每天背诵英语单词到深夜。")
    result = await run_compound(model)
    assert result["explanationMode"] == "rules"
    assert "放弃计算机" not in result["answer"]
    assert CombinedAnswer not in [schema for schema, _ in model.payloads]


def test_step_timeout_must_be_shorter_than_expert_stage():
    assert settings().CONVERSATION_STEP_TIMEOUT == 12
    with pytest.raises(ValueError, match="INVALID_STEP_TIMEOUT"):
        settings(CONVERSATION_STEP_TIMEOUT=28)
