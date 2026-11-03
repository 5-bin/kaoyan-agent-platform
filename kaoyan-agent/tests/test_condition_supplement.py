"""Regressions for condition-only follow-ups and model number grounding."""

import pytest

from agents.planning import ModelConversationResolution
from conversation import ConversationWorkflow
from grounding import numbers_supported
from learning import LearningAnswer
from tests.test_learning_privacy import engine, request


FACTS = '{"questionCount": 61, "correctCount": 17, "accuracy": 0.2786885245901639}'


def generic_clarification(text: str) -> ModelConversationResolution:
    return ModelConversationResolution(
        action="CHAT", standaloneQuery=text,
        clarification="请明确你想咨询的知识、择校条件或学习情况。",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "学硕", "081200学硕", "只考虑江苏", "2027年", "就学硕吧", "换成专硕", "学硕，北京优先", "北京上海都可以",
])
async def test_condition_supplement_is_resolved_by_rules_before_the_model(text):
    service = engine()
    service.model.generate.return_value = generic_clarification(text)
    req = request(userInput=text, privacy={"modelAllowed": True, "scopes": ["profile"]})
    plan = await ConversationWorkflow(service).plan(req)
    assert plan.action == "SCHOOL_RECOMMEND"
    assert plan.clarification is None
    assert plan.conditionPatch.model_fields_set
    service.model.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_degree_reply_fills_the_pending_school_condition():
    service = engine()
    service.model.generate.return_value = generic_clarification("学硕")
    req = request(userInput="学硕", privacy={"modelAllowed": True, "scopes": ["profile"]})
    plan = await ConversationWorkflow(service).plan(req)
    assert plan.conditionPatch.degreeType == "academic"


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "学硕和专硕有什么区别", "学硕吗", "刚才那个学硕",
    # Statements, negations, third parties and school names say more than a condition.
    "学硕不考了", "学硕难考", "我同学考学硕", "上海交大学硕", "学硕要考数学一", "学硕和专硕都行", "不只江苏",
])
async def test_questions_and_references_still_use_the_model_parser(text):
    service = engine()
    service.model.generate.return_value = ModelConversationResolution(action="CHAT", standaloneQuery=text)
    req = request(userInput=text, privacy={"modelAllowed": True, "scopes": ["profile"]})
    await ConversationWorkflow(service).plan(req)
    service.model.generate.assert_awaited_once()


@pytest.mark.parametrize("text", [
    "共作答61次，答对17次", "正确率约28%", "正确率约27.9%", "正确率27.87%", "答对17.0次",
])
def test_rounded_percentages_of_trusted_ratios_are_supported(text):
    assert numbers_supported(text, FACTS)


@pytest.mark.parametrize("text", ["答对1次", "答对18次", "正确率约27.8%", "共作答6次"])
def test_numbers_must_match_whole_trusted_values(text):
    # "1" and "6" occur inside "61" but are not trusted counts.
    assert not numbers_supported(text, FACTS)


@pytest.mark.asyncio
async def test_learning_answer_with_rounded_accuracy_is_not_downgraded():
    service = engine()
    service.model.generate.return_value = LearningAnswer(suggestions=[{"action": "PRACTICE_RELATED"}])
    req = request(
        privacy={"modelAllowed": True, "scopes": ["stats"]},
        learningContext={"statistics": {"questionCount": 61, "correctCount": 17, "accuracy": 17 / 61}},
        preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析统计", "reads": ["stats"]},
    )
    result = await ConversationWorkflow(service).run(req)
    assert result["explanationMode"] == "ai"
    assert "有效作答61次，正确17次" in result["answer"]
    assert "正确率27.9%" in result["answer"]


def learning_context():
    return {"statistics": {
        "questionCount": 61, "correctCount": 17, "accuracy": 17 / 61,
        "knowledgePoints": [{"knowledgePoint": "直接插入排序", "questionCount": 16, "correctCount": 5}],
        "learningProfile": {"revision": 3, "independentSamples": 8, "groups": [
            {"knowledgePoint": "直接插入排序", "difficulty": "中等", "samples": 8, "correct": 3},
        ]},
    }}


@pytest.mark.asyncio
async def test_rule_answer_labels_interval_attempts_and_profile_samples_separately():
    service = engine()
    req = request(
        privacy={"modelAllowed": False, "scopes": ["stats"]}, learningContext=learning_context(),
        preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析统计", "reads": ["stats"]},
    )
    answer = (await ConversationWorkflow(service).run(req))["answer"]
    assert "直接插入排序：作答16次，错11次，正确率31.2%" in answer
    assert "同题重复作答分别计数" in answer and "次数不能直接比较" in answer
    assert answer.index("作答16次") < answer.index("口径与上面的区间统计不同") < answer.index("画像复习优先")


@pytest.mark.asyncio
async def test_model_receives_code_computed_wrong_attempts_and_may_cite_them():
    service = engine()
    service.model.generate.return_value = LearningAnswer(suggestions=[{"action": "PRACTICE_RELATED"}])
    req = request(
        privacy={"modelAllowed": True, "scopes": ["stats"]}, learningContext=learning_context(),
        preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析统计", "reads": ["stats"]},
    )
    result = await ConversationWorkflow(service).run(req)
    stats = service.model.generate.call_args.args[1]["learningContext"]["statistics"]
    assert stats["wrongAttempts"] == 44
    assert stats["knowledgePoints"][0]["wrongAttempts"] == 11
    assert result["explanationMode"] == "ai"
    assert "错误44次" in result["answer"]
    assert "直接插入排序：作答16次，错11次" in result["answer"]


@pytest.mark.asyncio
async def test_model_arithmetic_beyond_supplied_facts_still_falls_back():
    service = engine()
    # 16 + 8 = 24 mixes two counting bases and is not a supplied fact.
    service.model.generate.return_value = LearningAnswer(answer="直接插入排序共练习24次。", evidenceRefs=[])
    req = request(
        privacy={"modelAllowed": True, "scopes": ["stats"]}, learningContext=learning_context(),
        preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析统计", "reads": ["stats"]},
    )
    result = await ConversationWorkflow(service).run(req)
    assert result["explanationMode"] == "fallback"
