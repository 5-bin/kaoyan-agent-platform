"""2026-11-02 composite answer quality: weak-point text, retrieval topics, plan wording and empty schools."""

from types import SimpleNamespace

import pytest

from agents.learning import mentions_topic
from agents.study import check_study_plan
from core.errors import InvalidModelOutput
from learning import rule_learning_answer, weak_point_topics
from schemas import ConversationResolution, StudyPlan
from tests.test_conversation import workflow
from tests.test_review_fixes import request


POINTS = [
    {"knowledgePoint": "调度时机", "questionCount": 1, "correctCount": 0},
    {"knowledgePoint": "简单选择排序", "questionCount": 5, "correctCount": 3},
    {"knowledgePoint": "堆排序", "questionCount": 3, "correctCount": 1},
    {"knowledgePoint": "直接插入排序", "questionCount": 16, "correctCount": 2},
    {"knowledgePoint": "栈", "questionCount": 2, "correctCount": 2},
]
PROFILE = {"revision": 12, "independentSamples": 46, "groups": [
    {"knowledgePoint": "调度时机", "difficulty": "MEDIUM", "samples": 1},
    {"knowledgePoint": "直接插入排序", "difficulty": "EASY", "samples": 8},
    {"knowledgePoint": "串", "difficulty": "HARD", "samples": 2, "anomaly": True},
]}


def rule_text() -> str:
    """Render the rule answer for a mixed interval with a profile."""
    stats = {"questionCount": 27, "correctCount": 8, "from": "2026-10-04", "to": "2026-11-02",
             "knowledgePoints": POINTS, "learningProfile": PROFILE}
    plan = ConversationResolution(action="LEARNING_ANALYSIS", standaloneQuery="分析薄弱点")
    return rule_learning_answer({"statistics": stats}, plan)


def test_rule_text_lists_judgeable_points_first_and_merges_small_samples():
    lines = rule_text().splitlines()
    assert "薄弱知识点（按区间错误率，前2个）：" in lines
    insertion = lines.index("直接插入排序：作答16次，错14次，正确率12.5%")
    selection = lines.index("简单选择排序：作答5次，错2次，正确率60.0%")
    assert insertion < selection
    merged = [line for line in lines if line.startswith("3个知识点作答样本不足5次")]
    assert len(merged) == 1
    assert merged[0].index("堆排序") < merged[0].index("栈") < merged[0].index("调度时机")
    assert not any(line.startswith("调度时机：") for line in lines)


def test_rule_text_has_no_conflicting_independent_line_or_raw_difficulty():
    text = rule_text()
    assert "学习时长与提示辅助未记录。" in text
    assert "独立作答：未记录" not in text
    assert "MEDIUM" not in text and "EASY" not in text and "HARD" not in text
    assert "画像复习优先（各组独立样本均不少于5条）：直接插入排序（简单）。" in text
    assert "串（困难）：独立样本2条，近期表现异常" in text
    assert "以下画像分组独立样本不足5条，建议补充独立样本：调度时机（中等，1条）。" in text


def test_merged_line_states_omitted_names():
    points = [{"knowledgePoint": f"知识点{i:02d}", "questionCount": 1, "correctCount": 0} for i in range(40)]
    plan = ConversationResolution(action="LEARNING_ANALYSIS", standaloneQuery="分析")
    text = rule_learning_answer({"statistics": {"questionCount": 40, "correctCount": 0, "knowledgePoints": points}}, plan)
    assert "等40个，其余30个未在文字中展示" in text


def test_many_points_show_only_the_weakest_and_skip_perfect_ones():
    """2026-11-03: 80 judgeable points render as a short list instead of 160 lines."""
    points = [{"knowledgePoint": f"弱{i:02d}", "questionCount": 5, "correctCount": i % 5} for i in range(60)]
    points += [{"knowledgePoint": f"全对{i:02d}", "questionCount": 5, "correctCount": 5} for i in range(20)]
    plan = ConversationResolution(action="LEARNING_ANALYSIS", standaloneQuery="分析")
    stats = {"questionCount": 400, "correctCount": 220, "knowledgePoints": points}
    lines = rule_learning_answer({"statistics": stats}, plan).splitlines()
    shown = [line for line in lines if line.startswith("弱") or line.startswith("全对")]
    assert len(shown) == 8
    assert all("错5次" in line for line in shown)
    assert "另有72个作答满5次的知识点未列出（其中20个区间内全部答对），完整分布见学习统计。" in lines
    assert len(lines) == 12  # facts, heading, 8 points, remainder, duration


def test_retrieval_topics_follow_weakness_not_alphabet():
    assert weak_point_topics(POINTS) == ["直接插入排序", "简单选择排序", "堆排序", "调度时机"]
    # Unknown correctness is kept; known zero wrong attempts is not a weak candidate.
    assert weak_point_topics([{"knowledgePoint": "线程", "questionCount": 3}]) == ["线程"]


def test_unrelated_reviewed_chunks_are_filtered():
    pipeline = SimpleNamespace(title="吞吐率、延迟与流水线性能", content="流水线通过让不同输入处于不同处理阶段……")
    sorting = SimpleNamespace(title="插入排序", content="直接插入排序把元素逐个插入有序区。")
    topics = ["直接插入排序", "冲突域与广播域"]
    assert mentions_topic(sorting, topics)
    assert not mentions_topic(pipeline, topics)
    assert mentions_topic(SimpleNamespace(title="广播域", content=""), topics)
    assert mentions_topic(pipeline, [])


@pytest.mark.parametrize("basis", [
    "学习画像状态为ACTIVE且sufficient为false",
    "直接插入排序masteryIndex偏低",
    "覆盖率coverage较低",
])
def test_study_plan_rejects_internal_field_names(basis):
    plan = StudyPlan(days=[{"day": 1, "topic": "直接插入排序", "tasks": ["复习有序区扩展过程"]}], basis=[basis])
    with pytest.raises(InvalidModelOutput, match="study_internal_field"):
        check_study_plan(plan, "{}", None, 1)


def test_study_plan_accepts_chinese_explanations():
    plan = StudyPlan(days=[{"day": 1, "topic": "直接插入排序", "tasks": ["复习有序区扩展过程"]}],
                     basis=["整体独立样本不足，薄弱结论需谨慎。"])
    check_study_plan(plan, "{}", None, 1)


@pytest.mark.asyncio
async def test_professional_with_academic_major_explains_empty_result():
    result = await workflow().run(request(
        "推荐院校", profile={"examYear": 2027, "targetMajor": "081200"},
        preferences={"degreeType": "professional", "explainWithAi": False}))
    assert result["outcome"] == "UNSUPPORTED"
    assert result["answer"].startswith("2027年资料共")
    assert "专业不匹配" in result["answer"] and "当前条件为专业081200、专硕" in result["answer"]
    assert any("085404" in hint and "改选学硕" in hint for hint in result["followUp"])


@pytest.mark.asyncio
async def test_missing_exam_year_data_is_not_called_2027():
    result = await workflow().run(request(
        "推荐院校", profile={"examYear": 2031, "targetMajor": "081200"},
        preferences={"degreeType": "academic", "explainWithAi": False}))
    assert result["answer"] == "当前资料没有2031年的招生项目，未替换为往年数据。"


@pytest.mark.asyncio
async def test_composite_notice_has_no_doubled_punctuation():
    result = await workflow().run(request("安排3天复习计划，并推荐院校"))
    assert result.get("notice")
    assert "。；" not in result["notice"] and "；；" not in result["notice"]
