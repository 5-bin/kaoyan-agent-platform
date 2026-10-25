"""Qdrant contract tests use explicit vectors; model quality is tested separately."""
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from config import Settings
from main import create_app
from learning import requested_knowledge_point, local_learning_plan
from question_search import QuestionIndex, SearchQuestion, SearchRequest, topic_matches
from conversation import ConversationWorkflow
from tests.test_learning_privacy import engine, request

KEY = 'test-only-internal-key-123456'
HEADERS = {'X-Internal-Key': KEY}


class FixtureEncoder:
    def encode(self, texts):
        return [[1., 0., 0.] if any(t in text for t in ('二叉树', '左右孩子', '至多两个分支'))
                else [0., 1., 0.] for text in texts]


def config(tmp_path):
    return Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY, QUESTION_INDEX=tmp_path)


def question(id, **values):
    return SearchQuestion(id=id, version=1, content=values.pop('content', '至多两个分支的结点'), **values)


def ready(index, questions):
    response = index.submit(questions)
    deadline = time.monotonic() + 8
    while index.status(response['releaseId'])['status'] == 'BUILDING':
        assert time.monotonic() < deadline
        time.sleep(.01)
    assert index.status(response['releaseId'])['status'] == 'READY'
    return response['releaseId']


@pytest.mark.parametrize('text,expected', [
    ('将错题本中涉及二叉树的题目加入收藏', '二叉树'),
    ('将错题本中涉及哈夫曼树内容的部分加入收藏', '哈夫曼树'),
    ('将错题本中知识点：二叉树的题目加入收藏', '二叉树'),
    ('知识点：“TCP流量控制”；将错题加入收藏', 'TCP流量控制'),
    ('搜索每个结点最多有两个孩子的题目', '每个结点最多有两个孩子'),
    ('搜索二叉树相关题', '二叉树'),
    ('找几道哈夫曼树题', '哈夫曼树'),
    ('关于进程与线程的题目', '进程与线程'),
    ('关于传输控制协议的题目', 'TCP'),
    ('涉及的题目加入收藏', None),
    ('涉及二叉树和队列的题目', None),
    ('涉及二叉树的题和涉及队列的题都加入收藏', None),
    ('知识点：二叉树；知识点：队列', None),
    ('涉及这个的题目', None),
])
def test_general_topic_extraction(text, expected):
    assert requested_knowledge_point(text) == expected


def test_public_search_is_a_read_and_collection_does_not_widen():
    plan = local_learning_plan('在全题库找关于二叉树的题目')
    assert plan.reads == ['questions'] and plan.target == 'normal' and plan.operation == 'NONE'
    assert local_learning_plan('从全题库创建5道关于二叉树的题目练习').operation == 'PRACTICE_CREATE'
    assert local_learning_plan('将错题本中涉及二叉树的题目加入收藏').reads == ['wrong']
    assert local_learning_plan('不要将错题本中涉及二叉树的题目加入收藏').operation == 'NONE'
    assert not topic_matches('TCP', 'ATCP')


@pytest.mark.asyncio
async def test_ready_zero_matches_does_not_invent_public_knowledge_or_call_model():
    service = engine()
    service.knowledge_search = AsyncMock()
    result = await ConversationWorkflow(service).run(request(
        userInput='在全题库搜索涉及未覆盖主题的题目',
        preparedPlan={'action': 'LEARNING_ANALYSIS', 'standaloneQuery': '未覆盖主题',
                      'reads': ['questions'], 'target': 'normal', 'knowledgePoint': '未覆盖主题'},
        learningContext={'items': [], 'total': 0, 'retrievalStatus': 'READY', 'matchTopic': '未覆盖主题'}))
    assert '没有找到符合该主题的题目' in result['answer']
    assert result['references'] == []
    service.knowledge_search.ainvoke.assert_not_awaited()
    service.model.generate.assert_not_awaited()


def test_immutable_index_authorization_union_and_ephemeral_overrides(tmp_path):
    index = QuestionIndex(config(tmp_path), encoder=FixtureEncoder())
    try:
        rows = [question(1, knowledgePoint='二叉树', content='标签命中'),
                question(2, knowledgePoint='遍历', content='左右孩子的访问顺序'),
                question(3, knowledgePoint='队列', content='先进先出'),
                question(4, knowledgePoint='普通树', content='多叉结构')]
        release = ready(index, rows)
        assert index.submit(list(reversed(rows)))['releaseId'] == release
        result = index.search(SearchRequest(releaseId=release, query='二叉树', allowedIds=[1, 2, 3]))
        assert [(r['id'], r['method']) for r in result['matches']] == [(1, 'LABEL'), (2, 'SEMANTIC')]
        assert [r['id'] for r in index.search(SearchRequest(releaseId=release, query='二叉树', allowedIds=[2]))['matches']] == [2]
        # Historical content replaces current content, rather than unioning versions.
        private = question(3, knowledgePoint='历史专用主题', content='左右孩子 PRIVATE_HISTORY_SENTINEL')
        result = index.search(SearchRequest(releaseId=release, query='二叉树', allowedIds=[2, 3], overrides=[private]))
        assert {r['id'] for r in result['matches']} == {2, 3}
        assert index.search(SearchRequest(releaseId=release, query='二叉树', allowedIds=[2], overrides=[question(2, content='队列')]))['matches'] == []
        replacement = [q.model_copy(update={'version': 2, 'content': '新题干'}) if q.id == 2 else q for q in rows]
        next_release = ready(index, replacement)
        assert next_release != release
        assert index.status(release)['status'] == 'READY'  # never deletes old collections
        assert index.search(SearchRequest(releaseId=next_release, query='二叉树', allowedIds=[2]))['matches'] == []
    finally:
        index.close()
    # Release Qdrant's exclusive Windows lock before inspecting every persisted file.
    for path in tmp_path.rglob('*'):
        if path.is_file():
            assert b'PRIVATE_HISTORY_SENTINEL' not in path.read_bytes()
    # Actual embedded Qdrant persistence survives process/client recreation.
    reopened = QuestionIndex(config(tmp_path), encoder=FixtureEncoder())
    try:
        assert reopened.status(release)['status'] == 'READY'
    finally:
        reopened.close()


def test_filter_before_limit_and_missing_snapshot_version(tmp_path):
    index = QuestionIndex(config(tmp_path), encoder=FixtureEncoder())
    try:
        rows = [question(i) for i in range(1, 76)]
        release = ready(index, rows)
        result = index.search(SearchRequest(releaseId=release, query='二叉树', allowedIds=[75]))
        assert result['total'] == 1 and result['matches'][0]['id'] == 75
        assert index.search(SearchRequest(releaseId=release, query='二叉树', allowedIds=[]))['matches'] == []
    finally:
        index.close()


def test_internal_auth_validation_and_failed_build(tmp_path):
    class BrokenEncoder:
        def encode(self, texts):
            raise RuntimeError('DO_NOT_EXPOSE')
    index = QuestionIndex(config(tmp_path), encoder=BrokenEncoder())
    with TestClient(create_app(config(tmp_path), model=AsyncMock(), question_index=index)) as client:
        assert client.post('/internal/rag/questions/index', json={'questions': []}).status_code == 401
        assert client.post('/internal/rag/questions/search', json={}).status_code == 401
        body = {'questions': [question(1).model_dump()]}
        contaminated = json.loads(json.dumps(body)); contaminated['questions'][0]['answer'] = 'secret'
        assert client.post('/internal/rag/questions/index', json=contaminated, headers=HEADERS).status_code == 422
        submitted = client.post('/internal/rag/questions/index', json=body, headers=HEADERS)
        assert submitted.headers['cache-control'] == 'no-store'
        release = submitted.json()['releaseId']
        deadline = time.monotonic() + 3
        while True:
            state = client.get('/internal/rag/questions/index/' + release, headers=HEADERS).json()
            if state['status'] != 'BUILDING':
                break
            assert time.monotonic() < deadline
        assert state['status'] == 'FAILED' and 'DO_NOT_EXPOSE' not in str(state)
        response = client.post('/internal/rag/questions/search', json={'releaseId': release, 'query': '二叉树', 'allowedIds': [1]}, headers=HEADERS)
        assert response.status_code == 503 and 'DO_NOT_EXPOSE' not in response.text
        response = client.post('/internal/rag/questions/search', json={'releaseId': release, 'query': '二叉树', 'allowedIds': [], 'overrides': [question(1).model_dump()]}, headers=HEADERS)
        assert response.status_code == 422
