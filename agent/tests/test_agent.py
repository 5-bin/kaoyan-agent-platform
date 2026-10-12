import json
from dataclasses import replace
from uuid import uuid4
import httpx
import pytest
from fastapi.testclient import TestClient
from agent_service.api import create_app
from agent_service.knowledge import KnowledgeBase
from agent_service.model_client import ModelClient
from agent_service.runner import Runner
from agent_service.schemas import ModelAnswer, RunRequest
from agent_service.settings import Settings
from agent_service.tools import inspect_text

KEY = "test-internal-key-123456789"


@pytest.fixture
def settings():
    return Settings(internal_key=KEY)


def request(text):
    return RunRequest(taskId=uuid4(), input=text)


def test_demo_has_sources_and_tool_results(settings):
    result = Runner(settings).run(request("请解释进程、线程与TCP可靠传输"))
    assert result.status == "completed" and result.mode == "demo"
    assert "未调用大模型" in result.answer and "文本统计工具" in result.answer
    assert {s.id for s in result.sources} == {"demo-os", "demo-cn"}


def test_unknown_topic_does_not_invent_sources(settings):
    result = Runner(settings).run(request("如何养殖海水观赏鱼并进行繁育"))
    assert result.status == "unsupported" and result.sources == []


def test_short_input_asks_for_details(settings):
    result = Runner(settings).run(request("帮帮我"))
    assert result.status == "needs_input" and result.followUp


def test_subject_filter_excludes_other_subjects(settings):
    body = RunRequest(taskId=uuid4(), input="请解释进程线程与TCP可靠传输", context={"subject": "operating_system"})
    result = Runner(settings).run(body)
    assert [source.id for source in result.sources] == ["demo-os"]


def test_tool_counts_lines_and_characters():
    assert inspect_text("a\n\n中文") == {"characters": 5, "nonemptyLines": 2}


def test_internal_endpoint_requires_key(settings):
    client = TestClient(create_app(settings))
    body = {"taskId": str(uuid4()), "input": "请解释进程与线程的概念区别"}
    assert client.post("/internal/run", json=body).status_code == 401
    assert client.post("/internal/run", headers={"X-Internal-Key": "wrong"}, json=body).status_code == 401
    response = client.post("/internal/run", headers={"X-Internal-Key": KEY}, json=body)
    assert response.status_code == 200 and response.json()["taskId"] == body["taskId"]


@pytest.mark.parametrize("changes", [{"input": "   "}, {"input": "x" * 8001}, {"taskId": "bad"}, {"ownerId": "forged"}])
def test_invalid_request_is_rejected(settings, changes):
    body = {"taskId": str(uuid4()), "input": "请解释进程与线程的概念区别", **changes}
    response = TestClient(create_app(settings)).post("/internal/run", headers={"X-Internal-Key": KEY}, json=body)
    assert response.status_code == 422


def test_health_and_docs_visibility(settings):
    client = TestClient(create_app(settings))
    assert client.get("/health").json()["mode"] == "demo"
    assert client.get("/docs").status_code == 404


def test_settings_require_explicit_internal_key():
    with pytest.raises(ValueError):
        Settings(internal_key="").validate()


def test_model_settings_require_https_and_credentials(settings):
    with pytest.raises(ValueError):
        replace(settings, mode="model", model_base_url="http://example.test").validate()


@pytest.mark.parametrize("bad_url", ["javascript:alert(1)", "//evil.test", "/references/../secret", "https://user:pass@example.test"])
def test_knowledge_rejects_unsafe_links(settings, tmp_path, bad_url):
    records = json.loads(settings.knowledge_path.read_text())
    records[0]["url"] = bad_url
    path = tmp_path / "sources.json"; path.write_text(json.dumps(records))
    with pytest.raises(ValueError):
        KnowledgeBase(path)


def test_duplicate_sources_rejected(settings, tmp_path):
    records = json.loads(settings.knowledge_path.read_text()); records.append(records[0])
    path = tmp_path / "sources.json"; path.write_text(json.dumps(records))
    with pytest.raises(ValueError):
        KnowledgeBase(path)


class FakeModel:
    def __init__(self, source_ids=None, error=None):
        self.source_ids = ["demo-os"] if source_ids is None else source_ids
        self.error = error

    def generate(self, payload, customized=True):
        if self.error:
            raise self.error
        assert payload["references"] and payload["toolResults"]
        return ModelAnswer(status="completed", answer="基于资料的结果", steps=["检查"], sourceIds=self.source_ids, followUp=[])


def test_model_result_uses_actual_source_metadata(settings):
    result = Runner(replace(settings, mode="model"), FakeModel()).run(request("请解释进程与线程的概念区别"))
    assert result.status == "completed" and result.mode == "model"
    assert result.sources[0].title.startswith("408工程演示")


@pytest.mark.parametrize("ids", [["invented"], []])
def test_model_invented_or_missing_source_fails(settings, ids):
    result = Runner(replace(settings, mode="model"), FakeModel(ids)).run(request("请解释进程与线程的概念区别"))
    assert result.status == "failed" and result.sources == []


def test_model_exception_does_not_expose_secret(settings):
    result = Runner(replace(settings, mode="model"), FakeModel(error=RuntimeError("secret-key-value"))).run(request("请解释进程与线程的概念区别"))
    assert result.status == "failed" and "secret-key-value" not in result.answer


def test_model_http_payload_and_daily_limit(settings, monkeypatch):
    settings = replace(settings, mode="model", model_base_url="https://model.example.test/v1", model_api_key="test-only-secret", model_name="test-model", max_model_calls_per_day=1)
    seen = []
    def respond(req):
        seen.append(json.loads(req.content))
        assert str(req.url) == "https://model.example.test/v1/chat/completions"
        answer = {"status": "completed", "answer": "结果", "steps": [], "sourceIds": ["demo-os"], "followUp": []}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(answer)}}]})
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs))
    model = ModelClient(settings)
    assert model.generate({"input": "示例"}).answer == "结果"
    assert seen[0]["model"] == "test-model" and seen[0]["max_tokens"] == 1500
    with pytest.raises(RuntimeError, match="model_daily_limit"):
        model.generate({"input": "第二次"})


@pytest.mark.parametrize("task_type", ["school_recommendation", "wrong_question_tutor"])
def test_pending_workflows_never_call_model(settings, task_type):
    body = RunRequest(taskId=uuid4(), input="请根据我的条件处理这个任务", taskType=task_type)
    result = Runner(settings, FakeModel(error=AssertionError("must not call model"))).run(body)
    assert result.status == "unsupported" and result.sources == []
    assert result.releaseId == "demo-408-v1"


@pytest.mark.parametrize("changes", [
    {"taskType": "invented"}, {"releaseId": "pretend-published"},
    {"context": {"ownerId": "forged"}}, {"context": {"subject": "finance"}},
    {"taskType": "school_recommendation", "context": {"subject": "operating_system"}},
])
def test_typed_contract_rejects_wrong_context(settings, changes):
    body = {"taskId": str(uuid4()), "input": "请解释进程与线程的概念区别", **changes}
    response = TestClient(create_app(settings)).post("/internal/run", headers={"X-Internal-Key": KEY}, json=body)
    assert response.status_code == 422


def test_legacy_request_remains_knowledge_qa():
    parsed = RunRequest(taskId=uuid4(), input="解释进程与线程的概念区别")
    assert parsed.taskType == "knowledge_qa" and parsed.context.subject is None
