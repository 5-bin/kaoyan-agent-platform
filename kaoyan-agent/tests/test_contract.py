from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
import main
from config import Settings
from main import create_app
from llm_client import ModelClient, ModelBudget
from schemas import Answer
from llm_client import _parse
from schemas import ChatRequest

KEY = 'test-only-internal-key-123456'
HEADERS = {'X-Internal-Key': KEY}
BODY = {'taskId': 'task-1', 'userId': 1, 'taskType': 'KNOWLEDGE_QA', 'userInput': '进程是什么'}

@pytest.fixture
def client(monkeypatch):
    app = create_app(Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY))
    app.state.engine.qa = AsyncMock(return_value={'outcome': 'UNSUPPORTED', 'answer': 'mock', 'references': []})
    with TestClient(app) as c:
        yield c


def test_internal_auth_is_http_401_and_never_calls_handler(client):
    assert client.post('/internal/rag/chat', json=BODY).status_code == 401
    assert client.post('/internal/rag/chat', json=BODY, headers={'X-Internal-Key': 'wrong'}).status_code == 401
    client.app.state.engine.qa.assert_not_called()


@pytest.mark.parametrize('changes', [
    {'taskType': 'invented'}, {'userInput': '  '}, {'userId': -1}, {'taskId': ''}, {'taskId': '../bad'},
    {'ownerId': 2}, {'userInput': 'x' * 8001}, {'correctQuestionIds': [1]},
])
def test_invalid_requests_rejected(client, changes):
    assert client.post('/internal/rag/chat', json={**BODY, **changes}, headers=HEADERS).status_code == 422
    client.app.state.engine.qa.assert_not_called()


def test_success_and_null_container_compatibility(client):
    response = client.post('/internal/rag/chat', json={**BODY, 'messages': None, 'profile': None}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['status'] == 'SUCCESS'
    assert response.json()['taskId'] == BODY['taskId']


@pytest.mark.parametrize('result', [{}, [], {'answer': 'mock', 'references': ['invented']}, {'other': 'wrong'}])
def test_malformed_or_untraceable_result_fails(client, monkeypatch, result):
    monkeypatch.setattr(client.app.state.engine, 'qa', AsyncMock(return_value=result))
    assert client.post('/internal/rag/chat', json=BODY, headers=HEADERS).json()['status'] == 'FAILED'


def test_upstream_failure_does_not_leak_details(client, monkeypatch, caplog):
    monkeypatch.setattr(client.app.state.engine, 'qa', AsyncMock(side_effect=RuntimeError('private-upstream-detail')))
    response = client.post('/internal/rag/chat', json=BODY, headers=HEADERS)
    assert response.json()['status'] == 'FAILED'
    assert 'private-upstream-detail' not in response.text + caplog.text


@pytest.mark.parametrize('correct,wrong', [([], []), ([1], [1]), ([-1], []), ([1, 1], [])])
def test_summary_requires_distinct_authorized_ids(correct, wrong):
    with pytest.raises(ValidationError):
        ChatRequest(taskId='t', userId=1, taskType='PRACTICE_SUMMARY', sessionId='s',
                    correctQuestionIds=correct, wrongQuestionIds=wrong)


def test_blank_internal_key_fails_configuration():
    with pytest.raises(ValueError):
        Settings(AGENT_INTERNAL_KEY='', _env_file=None)


@pytest.mark.parametrize('text', ['[]', '{}', 'null', 'not json'])
def test_model_output_must_be_nonempty_object(text):
    with pytest.raises((ValueError, TypeError)):
        _parse(text)


@pytest.mark.parametrize('task_type,method', [('SCHOOL_RECOMMEND','schools'), ('PRACTICE_SUMMARY','summary'), ('CHAT','resolve')])
def test_each_explicit_workflow_uses_its_own_handler(client, monkeypatch, task_type, method):
    body = {**BODY, 'taskType': task_type}
    if task_type == 'PRACTICE_SUMMARY':
        body.update(userInput=None, sessionId='session-1', questions=[])
    value = 'CHAT' if method == 'resolve' else {'outcome': 'NEEDS_INPUT', 'answer': 'mock'}
    handler = AsyncMock(return_value=value)
    monkeypatch.setattr(client.app.state.engine, method, handler)
    result = client.post('/internal/rag/chat', json=body, headers=HEADERS)
    assert result.status_code == 200
    assert result.json()['status'] == 'SUCCESS'
    handler.assert_awaited_once()
    client.app.state.engine.qa.assert_not_called()


@pytest.mark.asyncio
async def test_sdk_does_not_retry_failed_paid_requests(monkeypatch):
    import httpx
    import llm_client
    from openai import AsyncOpenAI, InternalServerError
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(500, json={'error': {'message': 'mock failure'}})
    monkeypatch.setattr(llm_client, 'AsyncOpenAI', lambda **kwargs: AsyncOpenAI(
        **kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))))
    config = Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY, LLM_ENABLED=True, LLM_API_KEY='test-only')
    model = ModelClient(config)
    try:
        with pytest.raises(InternalServerError):
            await model.generate('mock system', {}, Answer)
        assert len(requests) == 1
    finally:
        await model.close()


def test_summary_requires_distinct_snapshots_and_session():
    q = {'id': 1, 'subject': 'OS', 'content': 'mock stem', 'answer': 'A', 'correct': False}
    for body in ({'sessionId': 's', 'questions': [q, q]}, {'questions': [q]}):
        with pytest.raises(ValidationError):
            ChatRequest(taskId='t', userId=1, taskType='PRACTICE_SUMMARY', **body)


@pytest.mark.asyncio
@pytest.mark.parametrize('thinking_mode', ['default', 'enabled', 'disabled'])
@pytest.mark.parametrize('router', [False, True])
async def test_thinking_mode_reaches_vendor_without_changing_json_contract(thinking_mode, router):
    import json
    import httpx
    from openai import AsyncOpenAI
    requests = []
    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            'id': 'test-completion', 'object': 'chat.completion', 'created': 0,
            'model': 'test-only', 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': '{"answer":"测试回答","sourceIds":["test-source#0"]}'}}]})
    config = Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY, LLM_ENABLED=True,
        LLM_API_KEY='test-only', LLM_THINKING_MODE=thinking_mode)
    model = ModelClient(config)
    model.client = AsyncOpenAI(api_key='test-only', max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    try:
        answer = await model.generate('请输出JSON', {}, Answer, router=router)
        assert answer.answer == '测试回答'
        assert len(requests) == 1
        assert requests[0]['response_format'] == {'type': 'json_object'}
        assert requests[0]['model'] == (config.LLM_MODEL_ROUTER if router else config.LLM_MODEL_MAIN)
        if thinking_mode == 'default':
            assert 'thinking' not in requests[0]
        else:
            assert requests[0]['thinking'] == {'type': thinking_mode}
    finally:
        await model.close()


@pytest.mark.asyncio
async def test_model_daily_budget_blocks_before_opening_vendor_client(monkeypatch):
    import llm_client
    from unittest.mock import Mock
    config = Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY, LLM_ENABLED=True, LLM_API_KEY='test-only', MAX_MODEL_CALLS_PER_DAY=1)
    model = ModelClient(config)
    model.budget.consume(1)
    factory = Mock()
    monkeypatch.setattr(llm_client, 'AsyncOpenAI', factory)
    with pytest.raises(RuntimeError, match='上限'):
        await model.generate('system', {}, Answer)
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


@pytest.mark.parametrize('key', ['short', 'abcdefghijklmnop\n', 'abcdefghijklmnop '])
def test_non_printable_or_blank_internal_key_is_rejected(key):
    with pytest.raises(ValueError):
        Settings(_env_file=None, AGENT_INTERNAL_KEY=key)
