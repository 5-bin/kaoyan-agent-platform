from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
import main
from config import Settings, settings
from llm_client import _parse
from schemas import ChatRequest

HEADERS = {'X-Internal-Key': settings.AGENT_INTERNAL_KEY}
BODY = {'taskId': 'task-1', 'userId': 1, 'taskType': 'KNOWLEDGE_QA', 'userInput': '进程是什么'}

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main.wenda, 'handle', AsyncMock(return_value={'answer': 'mock', 'references': []}))
    return TestClient(main.app)


def test_internal_auth_is_http_401_and_never_calls_handler(client):
    assert client.post('/internal/rag/chat', json=BODY).status_code == 401
    assert client.post('/internal/rag/chat', json=BODY, headers={'X-Internal-Key': 'wrong'}).status_code == 401
    main.wenda.handle.assert_not_called()


@pytest.mark.parametrize('changes', [
    {'taskType': 'invented'}, {'userInput': '  '}, {'userId': -1}, {'taskId': ''},
    {'ownerId': 2}, {'userInput': 'x' * 8001}, {'correctQuestionIds': [1]},
])
def test_invalid_requests_rejected(client, changes):
    assert client.post('/internal/rag/chat', json={**BODY, **changes}, headers=HEADERS).status_code == 422
    main.wenda.handle.assert_not_called()


def test_success_and_null_container_compatibility(client):
    response = client.post('/internal/rag/chat', json={**BODY, 'messages': None, 'profile': None}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['status'] == 'SUCCESS'
    assert response.json()['taskId'] == BODY['taskId']


@pytest.mark.parametrize('result', [{}, [], {'answer': 'mock', 'references': ['invented']}, {'other': 'wrong'}])
def test_malformed_or_untraceable_result_fails(client, monkeypatch, result):
    monkeypatch.setattr(main.wenda, 'handle', AsyncMock(return_value=result))
    assert client.post('/internal/rag/chat', json=BODY, headers=HEADERS).json()['status'] == 'FAILED'


def test_upstream_failure_does_not_leak_details(client, monkeypatch, caplog):
    monkeypatch.setattr(main.wenda, 'handle', AsyncMock(side_effect=RuntimeError('private-upstream-detail')))
    response = client.post('/internal/rag/chat', json=BODY, headers=HEADERS)
    assert response.json()['status'] == 'FAILED'
    assert 'private-upstream-detail' not in response.text + caplog.text


@pytest.mark.parametrize('correct,wrong', [([], []), ([1], [1]), ([-1], []), ([1, 1], [])])
def test_summary_requires_distinct_authorized_ids(correct, wrong):
    with pytest.raises(ValidationError):
        ChatRequest(taskId='t', userId=1, taskType='PRACTICE_SUMMARY', sessionId='s',
                    correctQuestionIds=correct, wrongQuestionIds=wrong)


def test_blank_internal_key_fails_configuration():
    with pytest.raises(RuntimeError):
        Settings(AGENT_INTERNAL_KEY='', _env_file=None)


@pytest.mark.parametrize('text', ['[]', '{}', 'null', 'not json'])
def test_model_output_must_be_nonempty_object(text):
    with pytest.raises((ValueError, TypeError)):
        _parse(text)


@pytest.mark.parametrize('task_type', ['SCHOOL_RECOMMEND', 'PRACTICE_SUMMARY', 'CHAT'])
def test_each_explicit_workflow_uses_its_own_handler(client, monkeypatch, task_type):
    body = {**BODY, 'taskType': task_type}
    if task_type == 'PRACTICE_SUMMARY':
        body.update(userInput=None, sessionId='session-1', correctQuestionIds=[1], wrongQuestionIds=[2])
        handler = AsyncMock(return_value={'summary': 'mock summary', 'references': []})
        monkeypatch.setattr(main.summary, 'handle', handler)
    elif task_type == 'SCHOOL_RECOMMEND':
        handler = AsyncMock(return_value={'summary': 'mock recommendation', 'references': []})
        monkeypatch.setattr(main.tuijian, 'handle', handler)
    else:
        handler = AsyncMock(return_value={'answer': 'mock chat', 'references': []})
        monkeypatch.setattr(main, 'route', AsyncMock(return_value={'intent': 'CHANGUI'}))
        monkeypatch.setattr(main.changui, 'handle', handler)
    result = client.post('/internal/rag/chat', json=body, headers=HEADERS)
    assert result.status_code == 200
    assert result.json()['status'] == 'SUCCESS'
    handler.assert_awaited_once()
    main.wenda.handle.assert_not_called()


def test_sdk_does_not_retry_failed_paid_requests(monkeypatch):
    import asyncio
    import httpx
    import llm_client
    from openai import AsyncOpenAI, InternalServerError
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(500, json={'error': {'message': 'mock failure'}})
    monkeypatch.setattr(settings, 'LLM_API_KEY', 'test-only-model-key')
    monkeypatch.setattr(llm_client, 'AsyncOpenAI', lambda **kwargs: AsyncOpenAI(
        **kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))))
    with pytest.raises(InternalServerError):
        asyncio.run(llm_client.chat('mock-model', 'mock system', 'mock input'))
    assert len(requests) == 1


def test_summary_rejects_missing_or_foreign_questions(monkeypatch):
    import asyncio
    from handlers import summary
    req = ChatRequest(taskId='t', userId=1, taskType='PRACTICE_SUMMARY', sessionId='s',
                      correctQuestionIds=[1], wrongQuestionIds=[2])
    monkeypatch.setattr(summary, 'get_questions_by_ids', AsyncMock(return_value=[]))
    with pytest.raises(ValueError, match='题目'):
        asyncio.run(summary.handle(req))
    questions = [{'id': i, 'subject': 'OS', 'content': 'mock stem', 'answer': 'A', 'analysis': 'mock'} for i in [1, 2]]
    monkeypatch.setattr(summary, 'get_questions_by_ids', AsyncMock(return_value=questions))
    monkeypatch.setattr(summary, 'llm_chat', AsyncMock(return_value={
        'summary': 'mock', 'wrong_analysis': [{'question_id': 9}]}))
    with pytest.raises(ValueError, match='未授权'):
        asyncio.run(summary.handle(req))


def test_model_daily_budget_blocks_before_opening_vendor_client(monkeypatch):
    import asyncio
    import llm_client
    from unittest.mock import Mock
    limited = llm_client.ModelBudget()
    limited.consume(1)
    monkeypatch.setattr(llm_client, 'budget', limited)
    monkeypatch.setattr(settings, 'MAX_MODEL_CALLS_PER_DAY', 1)
    monkeypatch.setattr(settings, 'LLM_API_KEY', 'test-only-model-key')
    factory = Mock()
    monkeypatch.setattr(llm_client, 'AsyncOpenAI', factory)
    with pytest.raises(RuntimeError, match='上限'):
        asyncio.run(llm_client.chat('mock', 'system', 'user'))
    factory.assert_not_called()


def test_model_budget_changes_at_utc_date_boundary():
    from datetime import date
    from llm_client import ModelBudget
    day = [date(2026, 10, 14)]
    limited = ModelBudget(today=lambda: day[0])
    limited.consume(1)
    with pytest.raises(RuntimeError):
        limited.consume(1)
    day[0] = date(2026, 10, 15)
    limited.consume(1)
    assert limited.calls == 1


def test_concurrent_model_attempts_cannot_exceed_budget():
    from concurrent.futures import ThreadPoolExecutor
    from llm_client import ModelBudget
    limited = ModelBudget()
    def attempt(_):
        try:
            limited.consume(1)
            return True
        except RuntimeError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert sum(results) == 1
