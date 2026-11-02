"""Explicit practice commands use the reviewed bank, never model-generated questions."""
import pytest
from unittest.mock import AsyncMock
from learning import local_learning_plan
from conversation import ConversationWorkflow
from tests.test_learning_privacy import engine, request


@pytest.mark.parametrize('text,target,count,topic', [
    ('给我出几道有关排序的题', 'normal', 5, '排序'),
    ('给我出5道排序题', 'normal', 5, '排序'),
    ('给我出三道排序题', 'normal', 3, '排序'),
    ('从收藏里出5道排序题', 'favorite', 5, '排序'),
    ('从错题本中出三道有关排序的题', 'wrong', 3, '排序'),
    ('来几道二叉树的题', 'normal', 5, '二叉树'),
    ('给我出几道题', 'normal', 5, None),
])
def test_practice_intent(text, target, count, topic):
    plan = local_learning_plan(text)
    assert plan.operation == 'PRACTICE_CREATE'
    assert (plan.target, plan.count, plan.knowledgePoint) == (target, count, topic)
    assert not plan.clarification


@pytest.mark.parametrize('text', [
    '不要出题，解释排序', '如何出几道排序题', '例如：给我出5道排序题',
    '介绍一下出题功能', '帮我找有关排序的题', '出题功能有什么用', '出题功能是什么', '出题是什么',
])
def test_non_command_never_creates_practice(text):
    plan = local_learning_plan(text)
    assert plan is None or plan.operation == 'NONE'


@pytest.mark.parametrize('text', ['给我出三道排序和查找题', '给我出5道有关排序和查找的题', '给我出51道排序题', '给我出零道排序题'])
def test_ambiguous_or_invalid_requests_need_clarification(text):
    plan = local_learning_plan(text)
    assert plan.operation == 'NONE' and plan.clarification


@pytest.mark.asyncio
async def test_original_request_skips_model_and_knowledge_search():
    service = engine()
    service.knowledge_search = AsyncMock()
    req = request(userInput='给我出几道有关排序的题',
        learningContext={'retrievalStatus': 'READY', 'items': [{'ref': 'Q1', 'content': '审核题干', 'answered': False}]})
    result = await ConversationWorkflow(service).run(req)
    assert result['outcome'] == 'COMPLETED'
    service.model.generate.assert_not_awaited()
    service.knowledge_search.ainvoke.assert_not_awaited()
