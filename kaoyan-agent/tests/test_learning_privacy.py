"""Synthetic records only: privacy boundary and trusted-tool contract regressions."""
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from config import Settings
from main import create_app
from schemas import (ChatRequest, ConversationRequest, ConversationResolution,
                     DocumentDraft, Answer)
from learning import LearningAnswer, local_learning_plan, safe_learning_context
from conversation import ConversationWorkflow
from workflows import Workflows
from retrieval import Corpus, Retriever

KEY = "test-only-internal-key-123456"
HEADERS = {"X-Internal-Key": KEY}


def settings(**values):
    return Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY, LLM_ENABLED=True,
                    LLM_API_KEY="synthetic-test-only", **values)


def engine():
    config = settings()
    corpus = Corpus(config.RAG_DATA)
    return Workflows(config, corpus, Retriever(config, corpus), AsyncMock())


def request(**values):
    if "privacy" in values:
        values["privacy"] = {"provider": "https://open.bigmodel.cn/api/paas/v4", **values["privacy"]}
    return ConversationRequest(taskId="task-synthetic", userId=67123, taskType="CHAT",
        userInput=values.pop("userInput", "分析我的错题"), **values)


@pytest.mark.parametrize("text,operation,target,ordinal", [
    ("帮我收藏这道题", "FAVORITE_ADD", "selected", None),
    ("你帮我查看一下题号，并将其加入我的收藏", "FAVORITE_ADD", "selected", None),
    ("将其加入我的收藏", "FAVORITE_ADD", "selected", None),
    ("收藏题号 #26", "FAVORITE_ADD", "selected", None),
    ("收藏 Q1", "FAVORITE_ADD", "selected", None),
    ("收藏第二道题", "FAVORITE_ADD", "selected", 2),
    ("取消收藏这些题", "FAVORITE_REMOVE", "visible", None),
    ("把第三题移出错题", "WRONG_REMOVE", "selected", 3),
    ("用我的收藏安排10道题练习", "PRACTICE_CREATE", "favorite", None),
    ("帮我用收藏安排练习", "PRACTICE_CREATE", "favorite", None),
    ("从错题创建练习", "PRACTICE_CREATE", "wrong", None),
    ("帮我分析收藏题", "NONE", "selected", None),
    ("分析我的错题并推荐资料", "NONE", "selected", None),
    ("查看取消收藏的影响", "NONE", "selected", None),
    ("不要收藏这道题", "NONE", "selected", None),
    ("怎么取消收藏", "NONE", "selected", None),
    ("“帮我收藏这道题”这句话是什么意思", "NONE", "selected", None),
])
def test_current_instruction_separates_reads_from_writes(text, operation, target, ordinal):
    result = local_learning_plan(text)
    assert result.operation == operation
    assert result.target == target
    assert result.ordinal == ordinal


@pytest.mark.parametrize("topic,expected", [("tcp协议", "TCP"), ("TCP", "TCP"),
    ("t c p", "TCP"), ("传输控制协议", "TCP"), ("TCP序号", "TCP序号"),
    ("UDP", "UDP"), ("AVL树", "AVL树"), ("TCP流量控制", "TCP流量控制")])
def test_collection_topic_is_independent_of_favorite_destination(topic, expected):
    plan = local_learning_plan(f"将我错题本中涉及{topic}内容的部分加入我的收藏")
    assert plan.operation == "FAVORITE_ADD"
    assert plan.reads == ["wrong"] and plan.target == "wrong"
    assert plan.knowledgePoint == expected and not plan.clarification


def test_explicit_refs_keep_history_binding_and_unknown_topic_never_drops_filter():
    plan = local_learning_plan("将错题本中的 Q1 加入收藏")
    assert plan.target == "selected" and plan.questionRefs == ["Q1"]
    for text in ("将错题本中涉及未知主题的题加入收藏", "将错题本中涉及 TCP 和队列的题加入收藏", "将错题本中涉及 ATCP 的题加入收藏"):
        unclear = local_learning_plan(text)
        assert unclear.clarification and unclear.operation == "NONE"
    plan = local_learning_plan("将收藏列表中涉及 TCP 的题取消收藏")
    assert plan.target == "favorite" and plan.reads == ["favorite"]


@pytest.mark.asyncio
async def test_ambiguous_learning_request_offers_a_copyable_example_without_running_an_operation():
    service = engine()
    result = await ConversationWorkflow(service).run(request(
        userInput="将错题本中涉及未知主题的题加入收藏"))
    assert result["outcome"] == "NEEDS_INPUT"
    assert "知识点" in result["answer"] and "推荐问法" in result["answer"]
    assert "加入收藏" in result["answer"]
    service.model.generate.assert_not_awaited()


@pytest.mark.parametrize("text", ["从错题创建51道题练习", "从错题创建一百道题练习", "收藏第99题"])
def test_out_of_range_operation_requires_clarification(text):
    assert local_learning_plan(text).clarification


def test_plan_endpoint_local_read_and_write_without_model_or_sensitive_identifiers():
    model = AsyncMock()
    with TestClient(create_app(settings(), model=model)) as client:
        body = request(userInput="收藏第二道题").model_dump()
        assert client.post("/internal/rag/conversation/plan", json=body).status_code == 401
        response = client.post("/internal/rag/conversation/plan", headers=HEADERS, json=body)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["operation"] == "FAVORITE_ADD"
        assert response.json()["ordinal"] == 2
        assert "from" in response.json() and "from_" not in response.json()
        model.generate.assert_not_awaited()


def test_current_page_analysis_uses_filtered_page_context():
    flow = ConversationWorkflow(engine())
    req = request(userInput="分析当前页", pageContext={"page": "stat", "subject": "操作系统",
        "from": "2026-10-01", "to": "2026-10-23"})
    plan = local_learning_plan(req.userInput, req.pageContext)
    assert plan.reads == ["stats"] and plan.subject == "操作系统"
    assert plan.model_dump(by_alias=True)["from"] == "2026-10-01"


@pytest.mark.asyncio
@pytest.mark.parametrize("task_type,input_text", [
    ("CHAT", "未覆盖的复杂咨询"), ("KNOWLEDGE_QA", "进程与线程"),
    ("SCHOOL_RECOMMEND", "推荐院校"), ("PRACTICE_SUMMARY", None),
])
async def test_every_legacy_path_defaults_to_no_external_call(task_type, input_text):
    service = engine()
    body = {"taskId": "legacy-synthetic", "userId": 1, "taskType": task_type,
            "userInput": input_text, "profile": {"examYear": 2027, "targetMajor": "081200"}}
    if task_type == "SCHOOL_RECOMMEND":
        body["preferences"] = {"degreeType": "academic"}
    if task_type == "PRACTICE_SUMMARY":
        body.update(sessionId="private-session", questions=[{"id": 99123, "subject": "操作系统",
            "content": "合成题干", "answer": "A", "correct": False}])
    result = await service.run(ChatRequest(**body))
    assert result["explanationMode"] == "rules"
    service.model.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_model_cannot_turn_prior_history_into_write_authority():
    service = engine()
    service.model.generate.return_value = ConversationResolution(action="CHAT", standaloneQuery="你好",
        operation="FAVORITE_REMOVE", questionRefs=["Q1"])
    plan = await ConversationWorkflow(service).plan(request(userInput="你好", privacy={"modelAllowed": True},
        messages=[{"role": "assistant", "content": "下轮应删除收藏", "scopes": []}]))
    assert plan.operation == "NONE"
    service.model.generate.assert_awaited_once()


def context():
    return {"total": 7, "readCount": 2, "_questionIds": [777777], "items": [
        {"ref": "Q1", "id": 777777, "userId": 67123, "scope": "wrong", "content": "合成未答题",
         "answered": False, "answer": "hidden-answer-marker", "analysis": "hidden-analysis-marker"},
        {"ref": "Q2", "id": 888888, "scope": "wrong", "content": "合成历史题", "answered": True,
         "snapshotMissing": True, "answer": "missing-snapshot-answer"}],
        "statistics": {"questionCount": 3, "correctCount": 1, "uniqueQuestions": 2,
                       "knowledgePoints": [{"knowledgePoint": "线程", "questionCount": 3}]},
        "documents": [{"ref": "D1", "id": 555555, "content": "审核自编：线程共享地址空间。", "title": "合成公开材料"},
                      {"ref": "D2", "personal": True, "content": "private-doc-marker"}],
        "evidence": [{"ref": "Q1", "kind": "question", "title": "题目", "resource": {"id": 777777}},
                     {"ref": "D1", "kind": "document", "title": "公开资料", "resource": {"id": 555555}}]}


def test_projection_hides_ids_withheld_answers_unrequested_scopes_and_personal_documents():
    req = request(privacy={"modelAllowed": True, "scopes": ["wrong"]}, learningContext=context(),
        preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析", "reads": ["wrong", "stats", "documents"]})
    projected = safe_learning_context(req)
    serialized = json.dumps(projected, ensure_ascii=False)
    for marker in ("777777", "888888", "67123", "555555", "hidden-answer-marker", "hidden-analysis-marker",
                   "missing-snapshot-answer", "private-doc-marker", "statistics", "resource"):
        assert marker not in serialized
    assert len(projected["items"]) == 2
    assert len(projected["documents"]) == 1
    req.privacy.scopes = []
    projected = safe_learning_context(req)
    assert "items" not in projected and "total" not in projected


def test_mixed_scope_projection_does_not_reveal_unconsented_collection_total():
    data=context()
    data["items"][1]["scope"] = "favorite"
    data["scope"] = ["wrong", "favorite"]
    req=request(privacy={"modelAllowed": True, "scopes": ["favorite"]}, learningContext=data,
        preparedPlan={"action":"LEARNING_ANALYSIS", "standaloneQuery":"分析收藏与错题", "reads":["wrong", "favorite"]})
    projected=safe_learning_context(req)
    assert "total" not in projected and projected["readCount"] == 1
    assert len(projected["items"]) == 1 and projected["items"][0]["ref"] == "Q2"


def test_record_with_unknown_sensitivity_is_never_forwarded():
    data=context()
    for item in data["items"]:
        item.pop("scope")
    req=request(privacy={"modelAllowed":True,"scopes":["wrong"]},learningContext=data,
        preparedPlan={"action":"LEARNING_ANALYSIS","standaloneQuery":"分析错题","reads":["wrong"]})
    assert "items" not in safe_learning_context(req)


def test_practice_records_use_wrong_scope_without_discarding_authorized_items():
    req=request(privacy={"modelAllowed": True, "scopes": ["wrong"]}, learningContext=context(),
        preparedPlan={"action":"LEARNING_ANALYSIS", "standaloneQuery":"分析练习记录", "reads":["practice"]})
    assert len(safe_learning_context(req)["items"]) == 2


@pytest.mark.asyncio
async def test_unconsented_profile_conditions_and_background_are_absent_from_model_router():
    service = engine()
    service.model.generate.return_value = ConversationResolution(action="CHAT", standaloneQuery="你好")
    req = request(userInput="你好", privacy={"modelAllowed": True},
        conditions={"regions": ["private-region-marker"]},
        profile={"background": "private-background-marker", "targetSchool": "private-school-marker"})
    await ConversationWorkflow(service).plan(req)
    payload = json.dumps(service.model.generate.call_args.args[1])
    assert "private-" not in payload


@pytest.mark.asyncio
async def test_prepared_plan_calls_model_once_and_filters_revoked_and_unknown_history():
    service = engine()
    service.model.generate.return_value = LearningAnswer(answer="可能需要复习线程；仅3次作答，样本不足。", evidenceRefs=[])
    req = request(privacy={"modelAllowed": True, "scopes": ["stats"]}, learningContext=context(),
        preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析统计", "reads": ["stats", "wrong"]},
        messages=[{"role": "user", "content": "public-history", "scopes": []},
                  {"role": "assistant", "content": "revoked-wrong-marker", "scopes": ["wrong"]},
                  {"role": "assistant", "content": "unknown-legacy-marker"}])
    result = await ConversationWorkflow(service).run(req)
    assert result["explanationMode"] == "ai"
    service.model.generate.assert_awaited_once()
    payload = service.model.generate.call_args.args[1]
    sent = json.dumps(payload, ensure_ascii=False)
    assert "public-history" in sent
    for private in ("revoked-wrong-marker", "unknown-legacy-marker", "67123", "task-synthetic", "777777", "合成未答题"):
        assert private not in sent


@pytest.mark.asyncio
async def test_fabricated_learning_evidence_falls_back_to_facts_and_sample_warning():
    service = engine()
    service.model.generate.return_value = LearningAnswer(answer="unsupported-answer-marker", evidenceRefs=["unknown"])
    result = await ConversationWorkflow(service).run(request(privacy={"modelAllowed": True, "scopes": ["stats"]},
        learningContext=context(), preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析统计", "reads": ["stats"]}))
    assert result["explanationMode"] == "fallback"
    assert "样本不足5次" in result["answer"]
    assert "unsupported-answer-marker" not in result["answer"]


@pytest.mark.asyncio
async def test_document_alias_projection_preserves_real_java_target_only_in_proposal():
    service = engine()
    service.model.generate.return_value = DocumentDraft(title="合成笔记", content="更新后的合成内容")
    req = request(userInput="修改这份笔记", privacy={"modelAllowed": True, "scopes": ["document"]},
        document={"id": "real-document-123", "version": 3, "title": "合成笔记", "content": "original-document-marker"},
        preparedPlan={"action": "DOCUMENT_UPDATE", "standaloneQuery": "修改这份笔记"})
    result = await ConversationWorkflow(service).run(req)
    sent = json.dumps(service.model.generate.call_args.args[1])
    assert "real-document-123" not in sent and "D1" in sent
    assert result["documentProposal"]["documentId"] == "real-document-123"
    assert result["documentProposal"]["baseVersion"] == 3
    req.privacy.scopes = []
    service.model.generate.reset_mock()
    assert (await ConversationWorkflow(service).run(req))["outcome"] == "UNSUPPORTED"
    service.model.generate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("text,selected,action,reads", [
    ("新建一份错题汇总文档", False, "DOCUMENT_CREATE", ["wrong"]),
    ("根据当前我的薄弱点帮我改进一下该计划", True, "DOCUMENT_UPDATE", ["stats"]),
    ("按上述要求修改该文档", True, "DOCUMENT_UPDATE", []),
])
async def test_note_intent_precedes_learning_and_draft_receives_authorized_material(text, selected, action, reads):
    service = engine()
    service.model.generate.return_value = DocumentDraft(title="综合复习计划", content="# 合成草稿")
    note = {"id": "private-note", "title": "操作系统计划", "version": 2, "content": "原文必须保留"}
    req = request(userInput=text, document=note if selected else None,
        privacy={"modelAllowed": True, "scopes": ["wrong", "stats", "document"]},
        learningContext=context(), messages=[{"role": "user", "content": "每天30分钟", "scopes": []}])
    flow = ConversationWorkflow(service)
    plan = await flow.plan(req)
    assert plan.action == action and plan.reads == reads
    assert not plan.clarification
    req.preparedPlan = plan
    result = await flow.run(req)
    assert result["documentProposal"]["operation"] == ("update" if selected else "create")
    payload = service.model.generate.call_args.args[1]
    assert payload["messages"][0]["content"] == "每天30分钟"
    assert "private-note" not in json.dumps(payload)
    if selected:
        assert payload["document"]["content"] == "原文必须保留"
    if "stats" in reads:
        assert "statistics" in payload["learningContext"]
    # Revoked learning scopes cannot be smuggled into a document prompt.
    req.privacy.scopes = ["document"]
    await flow.run(req)
    payload = service.model.generate.call_args.args[1]
    assert not payload["learningContext"].get("statistics")
    assert not payload["learningContext"].get("items")


def test_topic_filter_and_non_commands_are_not_note_writes():
    from learning import local_document_plan
    assert local_learning_plan("把错题中跟堆有关的错题整理给我").knowledgePoint == "堆"
    assert local_document_plan("怎么新建一份错题笔记") is None
    assert local_document_plan("不要修改这份笔记", selected=True) is None


@pytest.mark.asyncio
async def test_existing_wrong_book_membership_is_acknowledged_without_a_model_or_write():
    service = engine()
    result = await ConversationWorkflow(service).run(request(userInput="帮我把堆有关错题加入错题本",
        privacy={"modelAllowed": True, "scopes": ["wrong"]},
        learningContext={"items": [{"ref": "Q1", "scope": "wrong", "inWrongBook": True,
            "knowledgePoint": "堆", "answered": True, "correct": 1, "snapshotMissing": False}],
            "scope": ["wrong"], "evidence": []}))
    assert "已在你的错题本" in result["answer"] and "最近一次已提交作答正确" in result["answer"]
    service.model.generate.assert_not_awaited()


def test_validation_errors_and_health_never_echo_sensitive_values():
    model = AsyncMock()
    with TestClient(create_app(settings(LLM_BASE_URL="https://name:secret@provider.invalid:443/v1/?token=secret#secret"), model=model)) as client:
        health = client.get("/health").json()
        assert health["provider"] == "https://provider.invalid/v1"
        body = request().model_dump()
        body["profile"] = {"background": "sensitive-marker", "unknown": "sensitive-marker"}
        response = client.post("/internal/rag/conversation/plan", headers=HEADERS, json=body)
        assert response.status_code == 422 and "sensitive-marker" not in response.text
        assert "input" not in response.json()["detail"][0]


@pytest.mark.asyncio
async def test_unknown_document_route_without_consent_never_calls_model():
    service = engine()
    result = await ConversationWorkflow(service).run(request(userInput="创建一份学习笔记"))
    assert result["outcome"] == "UNSUPPORTED"
    service.model.generate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [None, "https://other-provider.invalid/v1"])
async def test_missing_or_changed_provider_blocks_all_external_paths(provider):
    service=engine()
    req=request(privacy={"modelAllowed":True,"scopes":["stats","wrong","document","profile"],"provider":provider},
        learningContext=context())
    await ConversationWorkflow(service).run(req)
    req.userInput="修改这份笔记"
    req.document=__import__("schemas").PersonalDocument(id="synthetic-doc",version=1,title="笔记",content="合成内容")
    await ConversationWorkflow(service).run(req)
    req.taskType="KNOWLEDGE_QA";req.userInput="进程与线程"
    await service.run(req)
    service.model.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_chat_uses_local_intent_and_at_most_one_model_call():
    service=engine()
    service.model.generate.return_value=Answer(answer="线程共享地址空间。",sourceIds=["os-threads#0"])
    req=request(userInput="进程与线程",privacy={"modelAllowed":True})
    result=await service.run(req)
    assert result["explanationMode"]=="ai"
    service.model.generate.assert_awaited_once()
    assert "router" not in service.model.generate.call_args.kwargs
    service.model.generate.reset_mock()
    req.userInput="一个无法本地分类的新话题"
    assert (await service.run(req))["outcome"]=="NEEDS_INPUT"
    service.model.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_inherited_tracing_environment_and_callbacks_cannot_capture_model_payload(monkeypatch):
    import httpx
    import langsmith
    from openai import AsyncOpenAI
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.runnables.config import var_child_runnable_config
    from llm_client import ModelClient
    from langsmith.run_helpers import tracing_context
    records=[]
    class ContentSpy(BaseCallbackHandler):
        def on_chat_model_start(self,*args,**kwargs): records.append("callback-content")
        def on_chain_start(self,*args,**kwargs): records.append("callback-content")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2","true")
    monkeypatch.setenv("LANGSMITH_TRACING","true")
    monkeypatch.setenv("LANGSMITH_API_KEY","synthetic-trace-key")
    monkeypatch.setattr(langsmith.Client,"create_run",lambda *args,**kwargs:records.append("trace-content"))
    monkeypatch.setattr(langsmith.Client,"update_run",lambda *args,**kwargs:records.append("trace-content"))
    def provider(req):
        return httpx.Response(200,json={"id":"synthetic","object":"chat.completion","created":0,"model":"synthetic",
            "choices":[{"index":0,"finish_reason":"stop","message":{"role":"assistant","content":'{"answer":"合成回答","sourceIds":["source"]}'}}]})
    client=ModelClient(settings())
    client.client=AsyncOpenAI(api_key="synthetic",max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    token=var_child_runnable_config.set({"callbacks":[ContentSpy()]})
    try:
        with tracing_context(enabled=True):
            answer=await client.generate("合成指令",{"input":"synthetic-sensitive-marker"},Answer)
        assert answer.answer=="合成回答"
        assert records==[]
    finally:
        var_child_runnable_config.reset(token)
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("topic,source,concept", [
    ("队列","ds-deque#0","先进先出"),
    ("TCP","cn-tcp#0","确认"),
])
async def test_learning_analysis_grounds_concepts_in_existing_reviewed_408_corpus(topic,source,concept):
    service=engine()
    service.model.generate.return_value=LearningAnswer(answer=f"可能错因需要结合具体作答核对，先复习{topic}概念。",
        evidenceRefs=["Q1"],sourceIds=[source])
    data={"scope":["wrong"],"total":1,"readCount":1,
        "items":[{"ref":"Q1","scope":"wrong","answered":True,"snapshotMissing":False,
                  "knowledgePoint":topic,"content":"合成历史题干","userAnswer":"B","answer":"A","correct":False}],
        "evidence":[{"ref":"Q1","kind":"attempt","title":topic,"version":1,"locator":"合成历史快照"}]}
    req=request(privacy={"modelAllowed":True,"scopes":["wrong"]},learningContext=data,
        preparedPlan={"action":"LEARNING_ANALYSIS","standaloneQuery":"分析我的错题","reads":["wrong"]})
    result=await ConversationWorkflow(service).run(req)
    assert result["explanationMode"]=="ai"
    assert [ref["id"] for ref in result["references"]]==[source]
    assert concept in result["references"][0]["excerpt"]
    assert result["references"][0]["version"]=="knowledge-408-v1"
    payload=service.model.generate.call_args.args[1]
    assert source in [ref["id"] for ref in payload["references"]]
    assert "67123" not in json.dumps(payload) and "task-synthetic" not in json.dumps(payload)
    service.model.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_public_retrieval_query_never_uses_unconsented_private_topics():
    service=engine()
    service.knowledge_search=AsyncMock()
    service.knowledge_search.ainvoke.return_value=[]
    service.model.generate.return_value=LearningAnswer(answer="根据本轮公开资料复习。")
    data=context()
    data["items"][0]["knowledgePoint"]="private-topic-marker"
    data["statistics"]["knowledgePoints"][0]["knowledgePoint"]="private-stats-topic-marker"
    req=request(userInput="分析我的错题和备考资料",privacy={"modelAllowed":True,"scopes":[]},learningContext=data,
        preparedPlan={"action":"LEARNING_ANALYSIS","standaloneQuery":"分析我的错题和备考资料","reads":["wrong","stats","documents"]})
    await ConversationWorkflow(service).run(req)
    query=service.knowledge_search.ainvoke.call_args.args[0]["query"]
    assert "private-" not in query
    assert service.model.generate.call_args.args[1]["references"]==[]


@pytest.mark.asyncio
async def test_learning_model_cannot_fabricate_public_sources():
    service=engine()
    service.model.generate.return_value=LearningAnswer(answer="fabricated-concept-marker",sourceIds=["fake-source"])
    req=request(privacy={"modelAllowed":True,"scopes":["stats"]},learningContext=context(),
        preparedPlan={"action":"LEARNING_ANALYSIS","standaloneQuery":"分析统计","reads":["stats"]})
    result=await ConversationWorkflow(service).run(req)
    assert result["explanationMode"]=="fallback"
    assert "fabricated-concept-marker" not in result["answer"]
    assert result["references"][0]["id"]=="os-threads#0"
    assert "共享地址空间" in result["answer"]
