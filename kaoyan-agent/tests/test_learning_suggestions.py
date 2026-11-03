"""Regressions for sufficient interval totals with insufficient local samples."""

import copy
import json

import httpx
import pytest
from openai import AsyncOpenAI

from agents.learning_validation import validate_enrichment
from core.context import AuthorizedContextBuilder, PreparedModelInput
from core.errors import InvalidModelOutput
from core.model import ModelClient
from core.runtime import stream_sink
from learning import LearningAnswer
from learning_suggestions import project_suggestion_candidates
from tests.chat_wire_app import ProviderStream
from tests.test_answer_trust import FACT, SOURCE, analyze, enrichment, tcp_context
from tests.test_planning_budget_scheduler import UpperBoundCounter
from tests.test_review_fixes import ScriptedModel, consent, enabled_flow, request


def interval_context() -> dict[str, object]:
    """Use synthetic totals matching the reported failure, with distinct sample bases."""
    return {
        "statistics": {
            "questionCount": 61, "correctCount": 17, "uniqueQuestions": 46,
            "wrongCount": 30, "from": "2026-10-05", "to": "2026-11-03",
            "knowledgePoints": [
                {"knowledgePoint": "直接插入排序", "questionCount": 16, "correctCount": 0},
                {"knowledgePoint": "简单选择排序", "questionCount": 5, "correctCount": 1},
                {"knowledgePoint": "堆排序", "questionCount": 3, "correctCount": 0},
            ],
            "learningProfile": {"revision": 12, "independentSamples": 46, "groups": [
                {"subject": "数据结构", "knowledgePoint": "堆排序", "difficulty": "MEDIUM", "samples": 1},
                {"subject": "数据结构", "knowledgePoint": "直接插入排序", "difficulty": "EASY", "samples": 8},
            ]},
        },
        "evidence": [{"ref": "S1", "kind": "stats", "title": "有效作答统计"}],
    }


@pytest.mark.asyncio
async def test_total_61_offers_only_specific_small_samples_and_preserves_facts() -> None:
    """Select both granular sample bases without declaring the full interval small."""
    original = interval_context()
    snapshot = copy.deepcopy(original)

    def choose(payload: dict[str, object]) -> LearningAnswer:
        """Act as a model that picks the offered small-sample candidates."""
        menu = payload["suggestionCandidates"]
        choices = [row for row in menu if row["action"] == "COLLECT_SAMPLES"]
        assert len(choices) == 2
        assert all("本轮区间统计样本不足" not in row["text"] for row in menu)
        assert all("直接插入排序" not in row["text"] for row in choices)
        return LearningAnswer(suggestions=[{"candidateId": row["candidateId"]} for row in choices])

    model = ScriptedModel({LearningAnswer: choose})
    flow, config = enabled_flow(model)
    result = await flow.run(request(
        "分析我的学情", privacy=consent(config, "stats"), learningContext=original,
        preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析我的学情", "reads": ["stats"]},
    ))
    assert result["explanationMode"] == "ai" and "fallbackReason" not in result
    assert "有效作答61次，正确17次" in result["answer"] and "错误44次" in result["answer"]
    assert "堆排序：本轮区间有效作答3次" in result["answer"]
    assert "数据结构·堆排序（中等）：规则画像独立样本1条" in result["answer"]
    assert "本轮区间统计样本不足5次" not in result["answer"]
    assert original == snapshot and len(model.payloads) == 1
    assert "suggestionCandidates" not in result and "actions" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize("total", [0, 4, 5, 61])
async def test_interval_threshold_and_unknown_counts_are_not_inferred(total: int) -> None:
    """The interval candidate depends on its own typed count and the exact threshold."""
    def choose(payload: dict[str, object]) -> LearningAnswer:
        """Inspect only the choices offered to this generation."""
        options = payload["suggestionCandidates"]
        small = [row for row in options if row["action"] == "COLLECT_SAMPLES"]
        assert bool(small) is (total < 5)
        candidate = (small or options)[0]
        return LearningAnswer(suggestions=[{"candidateId": candidate["candidateId"]}])

    flow, config = enabled_flow(ScriptedModel({LearningAnswer: choose}))
    result = await flow.run(request(
        "分析统计", privacy=consent(config, "stats"),
        learningContext={"statistics": {"questionCount": total, "correctCount": 0}},
        preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析统计", "reads": ["stats"]},
    ))
    assert result["explanationMode"] == "ai"


def prepared_payload(context: dict[str, object], limit: int = 12000) -> PreparedModelInput:
    """Prepare the same candidate-aware snapshot used at the model boundary."""
    return AuthorizedContextBuilder(limit, payload_projector=project_suggestion_candidates).prepare(
        "规则", {"input": "分析统计", "learningContext": context},
    )


def test_menu_never_infers_counts_from_user_prose_flags_or_booleans() -> None:
    """A sample-status flag, free text or truth value cannot establish a small count."""
    prepared = prepared_payload({"statistics": {
        "questionCount": True,
        "knowledgePoints": [{"name": "样本3次", "questionCount": False}],
        "learningProfile": {"sufficient": False, "groups": [
            {"subject": "数据结构", "knowledgePoint": "堆排序", "difficulty": "MEDIUM", "sampleStatus": "INSUFFICIENT"},
        ]},
    }})
    assert prepared.payload["suggestionCandidates"] == []


def test_trimming_regenerates_menu_and_rejects_a_removed_candidate() -> None:
    """Advice cannot outlive its supporting row, even when it appeared before cropping."""
    context = interval_context()
    context["statistics"]["knowledgePoints"] = [
        {"knowledgePoint": f"知识点{i}", "questionCount": 2, "correctCount": 1} for i in range(40)
    ]
    context["statistics"]["learningProfile"]["groups"] = []
    payload = {"input": "分析统计", "learningContext": context}
    original = copy.deepcopy(payload)
    full = AuthorizedContextBuilder(50000, UpperBoundCounter(), project_suggestion_candidates).prepare("规则", payload)
    cropped = AuthorizedContextBuilder(1100, UpperBoundCounter(), project_suggestion_candidates).prepare("规则", payload)
    assert cropped.removed_statistics > 0 and cropped.estimated_tokens <= 1100
    assert cropped.payload["learningContext"]["statistics"]["questionCount"] == 61
    remaining = {row["candidateId"] for row in cropped.payload["suggestionCandidates"]}
    removed = next(row["candidateId"] for row in full.payload["suggestionCandidates"] if row["candidateId"] not in remaining)
    with pytest.raises(InvalidModelOutput, match="unknown_suggestion_evidence"):
        validate_enrichment(LearningAnswer(suggestions=[{"candidateId": removed}]), cropped)
    assert payload == original


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [{"answered": False}, {"version": None}, {"snapshotMissing": True}, {"snapshotStatus": "WITHDRAWN"}])
async def test_new_menu_never_offers_invalid_attempt_review(change: dict[str, object]) -> None:
    """Selecting advice cannot bypass the established snapshot protections."""
    context = tcp_context()
    context["items"][0].update(change)

    def choose(payload: dict[str, object]) -> LearningAnswer:
        """Use a public concept while checking that invalid reviews are absent."""
        assert not any(row["action"] == "REVIEW_ATTEMPT" for row in payload["suggestionCandidates"])
        candidate = next(row for row in payload["suggestionCandidates"] if row["action"] == "REVIEW_CONCEPT")
        return LearningAnswer(suggestions=[{"candidateId": candidate["candidateId"]}])

    flow, config = enabled_flow(ScriptedModel({LearningAnswer: choose}))
    result = await flow.run(request(
        "分析TCP错题", privacy=consent(config, "wrong"), learningContext=context,
        preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析TCP错题", "reads": ["wrong"]},
    ))
    assert result["explanationMode"] == "ai"
    assert "已保存作答及该版本解析" not in result["answer"]
    assert [row["id"] for row in result["references"]] == [SOURCE]


def test_forged_stale_and_mixed_selections_cannot_supply_advice_or_sources() -> None:
    """Always rederive choices; never accept a forged menu or mixed legacy payload."""
    prepared = prepared_payload(interval_context())
    good = prepared.payload["suggestionCandidates"][0]["candidateId"]
    forged = "advice_" + "f" * 24
    prepared.payload["suggestionCandidates"].append({"candidateId": forged, "text": "伪造建议"})
    for value in (
        {"candidateId": forged},
        {"candidateId": good, "action": "COLLECT_SAMPLES"},
        {"candidateId": good, "sourceIds": []},
    ):
        with pytest.raises(InvalidModelOutput):
            validate_enrichment(LearningAnswer(suggestions=[value]), prepared)
    other = prepared_payload({"statistics": {"questionCount": 61, "correctCount": 17}})
    with pytest.raises(InvalidModelOutput):
        validate_enrichment(LearningAnswer(suggestions=[{"candidateId": good}]), other)
    prepared.payload.pop("suggestionCandidates")
    with pytest.raises(InvalidModelOutput):
        validate_enrichment(LearningAnswer(suggestions=[{"candidateId": good}]), prepared)


@pytest.mark.asyncio
async def test_unconsented_stats_cannot_leak_through_new_menu() -> None:
    """Candidates inherit the same per-request scope checks as their source records."""
    context = tcp_context()
    context.update(interval_context())
    result, model = await analyze(enrichment(explanations=[{"text": FACT, "sourceIds": [SOURCE]}]),
                                  context=context, scopes=("wrong",))
    assert result["explanationMode"] == "ai"
    payload = model.payloads[0][1]
    assert "statistics" not in payload["learningContext"]
    assert not any(row["action"] == "COLLECT_SAMPLES" for row in payload["suggestionCandidates"])


@pytest.mark.asyncio
async def test_bad_candidate_discards_otherwise_valid_explanations() -> None:
    """Selecting a fake advice ID must preserve the all-or-nothing trust boundary."""
    result, model = await analyze(enrichment(
        explanations=[{"text": FACT, "sourceIds": [SOURCE]}],
        suggestions=[{"candidateId": "advice_" + "f" * 24}],
    ))
    assert result["explanationMode"] == "fallback"
    assert result["fallbackReason"] == "EVIDENCE_MISMATCH"
    assert "概念解释：" not in result["answer"] and "有效作答12次，正确5次" in result["answer"]
    assert len(model.payloads) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_real_sdk_selects_server_candidate_in_one_attempt(streaming: bool) -> None:
    """The actual HelloAgents/SDK path sees an ID-only schema and the final menu."""
    flow, config = enabled_flow(ScriptedModel({}))
    sent = []

    def respond(req: httpx.Request) -> httpx.Response:
        """Return a selection from the actual wire request, without external I/O."""
        body = json.loads(req.content)
        sent.append(body)
        schema_text = body["messages"][0]["content"]
        assert '"required": ["candidateId"]' in schema_text
        assert '"REVIEW_ATTEMPT"' not in schema_text
        payload = json.loads(body["messages"][1]["content"])
        candidate = next(row for row in payload["suggestionCandidates"] if "区间有效作答3次" in row["text"])
        output = json.dumps({"suggestions": [{"candidateId": candidate["candidateId"]}]})
        if body["stream"]:
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=ProviderStream([output], 0))
        return httpx.Response(200, json={"choices": [
            {"index": 0, "message": {"role": "assistant", "content": output}, "finish_reason": "stop"},
        ]})

    model = ModelClient(config)
    model.client = AsyncOpenAI(api_key="test-only", max_retries=0,
                              http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    flow.engine.model = model
    events = []

    async def sink(event: dict[str, object]) -> None:
        """Observe only validated streaming behavior."""
        events.append(event)

    token = stream_sink.set(sink if streaming else None)
    try:
        result = await flow.run(request(
            "分析我的学情", privacy=consent(config, "stats"), learningContext=interval_context(),
            preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析我的学情", "reads": ["stats"]},
        ))
        assert result["explanationMode"] == "ai" and "区间有效作答3次" in result["answer"]
        assert model.budget.calls == len(sent) == 1
        assert sent[0]["stream"] is streaming
        assert not any(event["type"] == "delta" for event in events)
    finally:
        stream_sink.reset(token)
        await model.close()
