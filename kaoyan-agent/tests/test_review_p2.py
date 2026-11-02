"""2026-11-02 P2 review regressions: study constraints, compound admission
turns, subject detection and read-only embedding weights."""

import pytest

import main
from agents.planning import ADMISSION_SPLIT, admission_compound
from agents.resolver import validate_plan
from config import Settings
from conversation import ConversationWorkflow
from core.admission_contract import load_sources
from core.errors import InvalidModelOutput, ToolUnavailable
from retrieval import Corpus, FastEmbedEncoder, Retriever, VectorIndex, subject_terms
from schemas import ConversationRequest, ConversationResolution, StudyPlan
from tests.test_conversation import KEY, workflow
from tests.test_learning_privacy import engine, request

# Shared verbatim with Java SchoolCatalogServiceTest.compoundAdmissionCases.
COMPOUND = [
    "查询北京大学招生信息并解释TCP可靠传输",
    "给我北京大学招生官网链接，并安排3天复习计划",
    "查询北京大学招生信息，再推荐几所类似院校",
    "查询北京大学招生目录，顺便做几道TCP题",
]
SINGLE = [
    "查询北京大学招生信息",
    "给我北京大学招生官网链接",
    "查询北京大学统计学专业招生信息",
    "查询北京大学计算机组成原理方向招生目录",
    "推荐南京审计大学并给我招生网址",
]


def study_request(text: str, *, model: bool = True) -> ConversationRequest:
    return request(
        userInput=text,
        privacy={"modelAllowed": model, "scopes": ["stats"]},
        learningContext={"statistics": {"questionCount": 12, "correctCount": 5}},
        preparedPlan={
            "action": "STUDY_PLAN", "standaloneQuery": text, "planVersion": 2, "studyDays": 3,
            "steps": [{"agent": "STUDY_PLAN", "dependsOn": []}], "reads": ["stats"],
        },
    )


def model_plan(*tasks: str, basis: tuple[str, ...] = ()) -> StudyPlan:
    return StudyPlan(
        days=[{"day": day, "topic": "线程", "tasks": [tasks[day - 1] if day <= len(tasks) else "复习审核资料"]}
              for day in (1, 2, 3)],
        basis=list(basis),
    )


def study_section(result: dict) -> dict:
    return next(item for item in result["sections"] if item["agent"] == "STUDY_PLAN")


@pytest.mark.asyncio
async def test_unrealistic_daily_hours_are_not_planned_as_given():
    service = engine()
    result = await ConversationWorkflow(service).run(study_request("安排3天复习计划，每天18小时", model=False))
    basis = result["studyPlan"]["basis"]
    assert any("每天18小时超出可持续上限12小时" in line for line in basis)
    assert not any("按你提供的每天18小时" in line for line in basis)


@pytest.mark.asyncio
@pytest.mark.parametrize(("text", "plan", "code"), [
    ("安排3天复习计划，每天2小时", model_plan("每天学习14小时，刷完线程专题"), "INVALID_OUTPUT"),
    ("安排3天复习计划", model_plan("学习线程2小时"), "INVALID_OUTPUT"),
    ("安排3天复习计划，每天2小时", model_plan("复习线程", basis=("目标408考到149分",)), "NUMBER_MISMATCH"),
    ("安排3天复习计划，每天2小时", model_plan("把正确率提升到90%"), "NUMBER_MISMATCH"),
    ("安排3天复习计划，每天2小时", model_plan("第5天复测线程"), "INVALID_OUTPUT"),
])
async def test_model_plans_breaking_constraints_fall_back(text, plan, code):
    service = engine()
    service.model.generate.return_value = plan
    result = await ConversationWorkflow(service).run(study_request(text))
    section = study_section(result)
    assert section["explanationMode"] == "fallback" and section["fallbackReason"] == code
    assert result["studyPlan"]["days"][0]["tasks"][0] == "复习审核资料中的定义与适用条件"


@pytest.mark.asyncio
async def test_compliant_model_plan_is_kept():
    service = engine()
    plan = model_plan("学习线程1.5小时，再练习30分钟", basis=("近期作答12次，正确5次，样本不足。",))
    service.model.generate.return_value = plan
    result = await ConversationWorkflow(service).run(study_request("安排3天复习计划，每天2小时"))
    assert study_section(result)["explanationMode"] == "ai"
    assert result["studyPlan"] == plan.model_dump()
    sent = service.model.generate.call_args.args[1]["constraints"]
    assert sent == {"hoursKnown": True, "availableMinutesPerDay": 120.0, "maxMinutesPerDay": 720}


@pytest.mark.parametrize("text", COMPOUND)
def test_compound_admission_detection(text):
    assert admission_compound(text)


@pytest.mark.parametrize("text", SINGLE)
def test_single_admission_requests_are_not_compound(text):
    assert not admission_compound(text)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", COMPOUND)
async def test_compound_admission_turn_asks_to_split_without_parameters(text):
    plan = await workflow().plan(ConversationRequest(taskId="t", userId=1, taskType="CHAT", userInput=text))
    assert plan.clarification == ADMISSION_SPLIT
    assert plan.schoolLookup is None and plan.admissionLinks is None
    assert not plan.reads and not plan.steps and plan.operation == "NONE"


@pytest.mark.asyncio
async def test_single_admission_requests_keep_their_routes():
    flow = workflow()
    lookup = await flow.plan(ConversationRequest(taskId="t", userId=1, taskType="CHAT", userInput=SINGLE[0]))
    assert lookup.action == "SCHOOL_LOOKUP" and lookup.schoolLookup.schoolName == "北京大学"
    links = await flow.plan(ConversationRequest(taskId="t", userId=1, taskType="CHAT", userInput=SINGLE[1]))
    assert links.action == "ADMISSION_LINKS" and links.admissionLinks is not None


def test_prepared_link_plan_for_a_compound_turn_is_rejected():
    code = next(source.code for source in load_sources().values() if source.name == "北京大学")
    req = ConversationRequest(taskId="t", userId=1, taskType="CHAT", userInput=COMPOUND[1])
    forged = ConversationResolution(action="ADMISSION_LINKS", standaloneQuery=COMPOUND[1],
                                    admissionLinks={"schoolCode": code})
    with pytest.raises(InvalidModelOutput):
        validate_plan(forged, req)


@pytest.mark.parametrize(("text", "subject"), [
    ("解释计算机网络中的TCP协议栈", "计算机网络"),
    ("TCP协议栈", "计算机网络"),
    ("TCP/IP模型", "计算机网络"),
    ("pipeline怎么设计", None),
    ("栈和队列有什么区别", "数据结构"),
])
def test_full_terms_and_explicit_subjects_win(text, subject):
    assert subject_terms(text)[0] == subject


@pytest.mark.asyncio
async def test_chunks_sharing_only_weak_words_are_not_answers():
    # The demo corpus has a deque/stack chunk and a TCP chunk, neither about "协议栈".
    result = await workflow().run(ConversationRequest(
        taskId="t", userId=1, taskType="KNOWLEDGE_QA", userInput="协议栈的分层结构"))
    assert result["outcome"] == "UNSUPPORTED"
    assert not result.get("references")


@pytest.mark.asyncio
async def test_relevant_chunks_still_answer():
    result = await workflow().run(ConversationRequest(
        taskId="t", userId=1, taskType="KNOWLEDGE_QA", userInput="解释计算机网络中的TCP协议栈"))
    assert result["outcome"] == "COMPLETED"
    assert [ref["id"].split("#")[0] for ref in result["references"]] == ["cn-tcp"]


def test_serving_retriever_never_downloads_weights(monkeypatch):
    created = {}

    class Recorder(Retriever):
        def __init__(self, settings, corpus, local_files_only=False):
            created["local_files_only"] = local_files_only
            super().__init__(settings, corpus, local_files_only=local_files_only)

    monkeypatch.setattr(main, "Retriever", Recorder)
    main.create_app(Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY))
    assert created == {"local_files_only": True}


def test_missing_weight_cache_is_tool_unavailable(monkeypatch):
    import fastembed

    class Missing(fastembed.TextEmbedding):
        """Keeps the class API qdrant_client inspects; only loading fails."""

        def __init__(self, **kwargs):
            raise ValueError("Could not load model from any source.")

    monkeypatch.setattr(fastembed, "TextEmbedding", Missing)
    with pytest.raises(ToolUnavailable):
        FastEmbedEncoder("BAAI/bge-small-zh-v1.5", local_files_only=True)
    with pytest.raises(ValueError):
        FastEmbedEncoder("BAAI/bge-small-zh-v1.5", local_files_only=False)


def test_hybrid_falls_back_when_index_exists_but_weights_are_missing(monkeypatch, tmp_path):
    import fastembed

    class Missing(fastembed.TextEmbedding):
        """Keeps the class API qdrant_client inspects; only loading fails."""

        def __init__(self, **kwargs):
            raise ValueError("Could not load model from any source.")

    monkeypatch.setattr(fastembed, "TextEmbedding", Missing)
    config = Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY, RAG_BACKEND="hybrid", RAG_INDEX=tmp_path,
                      QUESTION_MODEL_CACHE=tmp_path / "embedding", RAG_MIN_SCORE=0)
    corpus = Corpus(config.RAG_DATA)
    # A ready marker and store exist, so only the weight cache is missing.
    builder = VectorIndex(config, corpus)
    builder.marker.write_text("{}", encoding="utf-8")
    builder.close()
    retriever = Retriever(config, corpus, local_files_only=True)
    try:
        found = retriever.search("TCP可靠传输")
        assert found and found[0].id.startswith("cn-tcp")
    finally:
        retriever.close()
