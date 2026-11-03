"""Independent adversarial and successful cases for answer adoption boundaries."""

import asyncio
from collections.abc import AsyncIterator
import json

import httpx
import pytest
from openai import AsyncOpenAI

from core.context import AuthorizedContextBuilder
from core.errors import InvalidModelOutput
from core.model import ModelClient
from core.runtime import stream_sink
from grounding import fully_supported, score_claim, verify
from learning import LearningAnswer
from schemas import Answer, Claim, CombinedAnswer
from tests.test_review_fixes import ScriptedModel, consent, enabled_flow, request
from tests.chat_wire_app import ProviderStream

SOURCE = "cn-tcp#0"
FACT = "TCP通过序号、确认和重传恢复丢失。"


def enrichment(**changes: object) -> LearningAnswer:
    """Author a schema-checked provider response, never a trusted final result."""
    return LearningAnswer.model_validate(changes or {"explanations": [{"text": FACT, "sourceIds": [SOURCE]}]})


async def analyze(generated: LearningAnswer, *, context: dict[str, object] | None = None, text: str = "分析我的学情", scopes: tuple[str, ...] = ("stats",), messages: list[dict[str, object]] | None = None) -> tuple[dict[str, object], ScriptedModel]:
    """Run the real coordinator/expert with a deterministic one-attempt provider."""
    model = ScriptedModel({LearningAnswer: generated})
    flow, config = enabled_flow(model)
    req = request(text, privacy=consent(config, *scopes), messages=messages or [],
                  learningContext=context or {"statistics": {"questionCount": 12, "correctCount": 5}},
                  preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": text,
                                "reads": ["stats", "wrong"]})
    return await flow.run(req), model


@pytest.mark.asyncio
@pytest.mark.parametrize("answer,claims", [
    (FACT + "TCP默认端口为99999。", [FACT]),
    (FACT + "错误。", [FACT]),
    (FACT, ["TCP不通过序号、确认和重传恢复丢失。"]),
    (FACT + "确认用于恢复丢失。", ["确认用于恢复丢失。", FACT]),
])
async def test_claims_cannot_hide_extra_changed_short_or_reordered_body(answer: str, claims: list[str]) -> None:
    """Claims cannot hide extra changed short or reordered body."""
    model = ScriptedModel({Answer: Answer(answer=answer, sourceIds=[SOURCE],
                                         claims=[Claim(text=text, sourceIds=[SOURCE]) for text in claims])})
    flow, config = enabled_flow(model)
    result = await flow.engine.qa(request("TCP可靠传输", privacy=consent(config)))
    assert result["explanationMode"] == "fallback"
    assert result["fallbackReason"] == "EVIDENCE_MISMATCH"
    assert result["answer"].startswith("以下为来源摘要")


@pytest.mark.asyncio
async def test_formatted_complete_claims_and_legacy_grounded_text_pass() -> None:
    """Formatted complete claims and legacy grounded text pass."""
    for claims in ([Claim(text=FACT, sourceIds=[SOURCE])], []):
        model = ScriptedModel({Answer: Answer(answer="- **" + FACT + "** [" + SOURCE + "]", sourceIds=[SOURCE], claims=claims)})
        flow, config = enabled_flow(model)
        result = await flow.engine.qa(request("TCP可靠传输", privacy=consent(config)))
        assert result["explanationMode"] == "ai"
        assert fully_supported(result["citationSupport"])


@pytest.mark.parametrize("claim", ["CPU容量为1字节。", "CPU容量为6字节。", "CPU容量为6.1字节。"])
def test_source_numbers_are_whole_values(claim: str) -> None:
    """Source numbers are whole values."""
    _, reason = score_claim(claim, [{"content": "CPU容量为61字节。"}])
    assert reason == "number_mismatch"


def test_short_claims_cannot_skip_number_checks() -> None:
    """Short claims cannot skip number checks."""
    report = verify("TCP端口99。", [SOURCE], {SOURCE: {"content": FACT}},
                    claims=[{"text": "TCP端口99。", "sourceIds": [SOURCE]}], strict=True)
    assert report["checked"] == 1 and not fully_supported(report)


@pytest.mark.asyncio
@pytest.mark.parametrize("generated", [
    LearningAnswer(answer="你已完成1000题，正确率98%。"),
    enrichment(explanations=[{"text": "你的正确率为98%。", "sourceIds": [SOURCE]}]),
])
async def test_question_and_history_numbers_cannot_become_statistics(generated: LearningAnswer) -> None:
    """Question and history numbers cannot become statistics."""
    result, _ = await analyze(generated, text="分析我的学情，我是否已经做了1000题且正确率98%？",
                             messages=[{"role": "assistant", "content": "你已完成1000题，正确率98%。", "scopes": ["stats"]}])
    assert result["explanationMode"] == "fallback"
    assert "1000" not in result["answer"] and "98%" not in result["answer"]
    assert "有效作答12次，正确5次" in result["answer"]


@pytest.mark.asyncio
async def test_rule_facts_survive_successful_enrichment_and_suggestions_do_not_create_actions() -> None:
    """Rule facts survive successful enrichment and suggestions do not create actions."""
    result, model = await analyze(enrichment(suggestions=[{"action": "COLLECT_SAMPLES"}]),
                                  context={"statistics": {"questionCount": 3, "correctCount": 1, "accuracy": 1 / 3}})
    assert result["explanationMode"] == "ai"
    assert "有效作答3次，正确1次" in result["answer"]
    assert "错误2次" in result["answer"] and "正确率33.3%" in result["answer"]
    assert "样本不足5次" in result["answer"]
    assert result["citationSupport"]["status"] == "NOT_CHECKED"
    assert "actions" not in result and len(model.payloads) == 1
    assert set(LearningAnswer.model_json_schema()["properties"]) == {"explanations", "suggestions"}


@pytest.mark.asyncio
async def test_learning_concept_always_checked_with_its_own_source() -> None:
    """Learning concept always checked with its own source."""
    for source, text in ((SOURCE, "TCP使用三次握手建立连接。"), ("os-threads#0", FACT)):
        result, _ = await analyze(enrichment(explanations=[{"text": text, "sourceIds": [source]}]),
                                  context=tcp_context(), scopes=("wrong",))
        assert result["explanationMode"] == "fallback" and "概念解释：" not in result["answer"]


def tcp_context() -> dict[str, object]:
    """A fully graded synthetic snapshot with one authorized evidence alias."""
    return {"scope": ["wrong"], "total": 1, "readCount": 1,
            "items": [{"ref": "Q1", "scope": "wrong", "answered": True, "version": 2,
                       "knowledgePoint": "TCP", "content": "合成题干", "correct": False,
                       "userAnswer": "B", "answer": "A"}],
            "evidence": [{"ref": "Q1", "kind": "attempt", "title": "TCP", "version": 2}]}


@pytest.mark.asyncio
async def test_valid_learning_concepts_and_graded_review_are_kept_together() -> None:
    """Valid learning concepts and graded review are kept together."""
    output = enrichment(explanations=[{"text": FACT, "sourceIds": [SOURCE]}],
                        suggestions=[{"action": "REVIEW_ATTEMPT", "evidenceRefs": ["Q1"]},
                                     {"action": "REVIEW_CONCEPT", "sourceIds": [SOURCE]},
                                     {"action": "PRACTICE_RELATED", "evidenceRefs": ["Q1"]}])
    result, _ = await analyze(output, context=tcp_context(), scopes=("wrong",))
    assert result["explanationMode"] == "ai" and FACT in result["answer"]
    assert "回顾[Q1]" in result["answer"] and "预览并确认" in result["answer"]
    assert fully_supported(result["citationSupport"])
    assert [row["id"] for row in result["references"]] == [SOURCE]
    assert "explanations" not in result and "suggestions" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize("suggestion", [
    {"action": "REVIEW_CONCEPT"},
    {"action": "REVIEW_ATTEMPT", "evidenceRefs": ["Q2"]},
    {"action": "COLLECT_SAMPLES"},
    {"action": "PRACTICE_RELATED", "sourceIds": ["unknown"]},
])
async def test_bad_suggestion_discards_valid_explanations_too(suggestion: dict[str, object]) -> None:
    """Bad suggestion discards valid explanations too."""
    result, _ = await analyze(enrichment(explanations=[{"text": FACT, "sourceIds": [SOURCE]}], suggestions=[suggestion]))
    assert result["explanationMode"] == "fallback" and "概念解释：" not in result["answer"]


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [{"answered": False}, {"snapshotMissing": True}, {"snapshotStatus": "WITHDRAWN"}, {"answer": None}, {"version": None}])
async def test_review_requires_an_available_graded_snapshot(changes: dict[str, object]) -> None:
    """Review requires an available graded snapshot."""
    context = tcp_context()
    context["items"][0].update(changes)
    result, _ = await analyze(enrichment(suggestions=[{"action": "REVIEW_ATTEMPT", "evidenceRefs": ["Q1"]}]),
                              context=context, scopes=("wrong",))
    assert result["explanationMode"] == "fallback"


@pytest.mark.asyncio
async def test_unconsented_statistics_are_local_only_and_never_summarized_again() -> None:
    """Unconsented statistics are local only and never summarized again."""
    model = ScriptedModel({LearningAnswer: enrichment(explanations=[{"text": FACT, "sourceIds": [SOURCE]}]),
                           Answer: Answer(answer=FACT, sourceIds=[SOURCE]),
                           CombinedAnswer: CombinedAnswer(answer="untrusted-rewrite")})
    flow, config = enabled_flow(model)
    context = tcp_context()
    context["statistics"] = {"questionCount": 1000, "correctCount": 98}
    result = await flow.run(request("分析学情并解释TCP可靠传输", privacy=consent(config, "wrong"), learningContext=context,
        preparedPlan={"action": "MULTI_AGENT", "planVersion": 2, "standaloneQuery": "分析学情并解释TCP可靠传输",
                      "steps": [{"agent": "LEARNING"}, {"agent": "KNOWLEDGE"}], "reads": ["wrong", "stats"]}))
    assert "有效作答1000次" in result["answer"]
    assert all("statistics" not in payload.get("learningContext", {}) for _, payload in model.payloads)
    assert CombinedAnswer not in [schema for schema, _ in model.payloads]
    assert result["citationSupport"]["checked"] >= 2


@pytest.mark.asyncio
async def test_visible_cropped_source_is_the_only_explanation_basis() -> None:
    """Visible cropped source is the only explanation basis."""
    from agents.learning_validation import validate_enrichment

    text = "TCP确认重传。" * 600 + "协议特有的末尾事实无法从前文推出。"
    prepared = AuthorizedContextBuilder(1800).prepare("规则", {
        "input": "TCP", "learningContext": {}, "references": [{"id": SOURCE, "content": text}]})
    assert prepared.shortened_excerpts == 1
    with pytest.raises(InvalidModelOutput):
        validate_enrichment(enrichment(explanations=[{"text": "协议特有的末尾事实无法从前文推出。", "sourceIds": [SOURCE]}]), prepared)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["knowledge", "learning"])
async def test_pending_deltas_are_withheld_until_result_validation(kind: str) -> None:
    """Pending deltas are withheld until result validation."""
    model = ScriptedModel({})
    flow, config = enabled_flow(model)

    async def generate(instruction: str, payload: dict[str, object], schema: type, **kwargs: object) -> Answer | LearningAnswer:
        """Generate."""
        await stream_sink.get()({"type": "delta", "slot": "answer", "offset": 0, "text": "untrusted99999"})
        if kind == "knowledge":
            return Answer(answer=FACT + "端口99999。", sourceIds=[SOURCE])
        return LearningAnswer(answer="你已作答99999次。")

    model.generate = generate
    events = []
    async def sink(event: dict[str, object]) -> None:
        """Sink."""
        events.append(event)
    token = stream_sink.set(sink)
    try:
        if kind == "knowledge":
            result = await flow.engine.qa(request("TCP可靠传输", privacy=consent(config)))
        else:
            result = await flow.run(request("分析统计", privacy=consent(config, "stats"),
                learningContext={"statistics": {"questionCount": 12, "correctCount": 5}},
                preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析统计", "reads": ["stats"]}))
        assert result["explanationMode"] == "fallback" and "99999" not in result["answer"]
        assert not any(event["type"] == "delta" for event in events)
    finally:
        stream_sink.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["knowledge", "learning"])
@pytest.mark.parametrize("termination", ["cancel", "timeout"])
async def test_withheld_real_sdk_stream_still_closes_and_counts_attempt(kind: str, termination: str) -> None:
    """Withheld real sdk stream still closes and counts attempt."""
    started, closed = asyncio.Event(), asyncio.Event()

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            """  aiter  ."""
            started.set()
            chunk = {"choices": [{"index": 0, "delta": {"content": '{"answer":"untrusted99999'}, "finish_reason": None}]}
            yield ("data: " + json.dumps(chunk) + "\n\n").encode()
            await asyncio.Event().wait()

        async def aclose(self) -> None:
            """Aclose."""
            closed.set()

    flow, config = enabled_flow(ScriptedModel({}))
    model = ModelClient(config)
    model.client = AsyncOpenAI(api_key="test-only", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=SlowStream()))))
    flow.engine.model = model
    events = []
    async def sink(event: dict[str, object]) -> None:
        """Sink."""
        events.append(event)
    token = stream_sink.set(sink)
    req = request("TCP可靠传输" if kind == "knowledge" else "分析统计", privacy=consent(config, "stats"),
        learningContext={"statistics": {"questionCount": 12, "correctCount": 5}},
        preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析统计", "reads": ["stats"]})
    task = asyncio.create_task(flow.engine.qa(req) if kind == "knowledge" else flow.run(req))
    try:
        await asyncio.wait_for(started.wait(), 1)
        if termination == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(task, 0.02)
        assert closed.is_set()
        assert model.budget.calls == 1
        assert not any(event["type"] == "delta" for event in events)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        stream_sink.reset(token)
        await model.close()


@pytest.mark.asyncio
async def test_structured_learning_runs_through_real_sdk_and_preserves_final_envelope() -> None:
    """Structured learning runs through real sdk and preserves final envelope."""
    flow, config = enabled_flow(ScriptedModel({}))
    sent = []

    def respond(req: httpx.Request) -> httpx.Response:
        """Respond."""
        sent.append(json.loads(req.content))
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              stream=ProviderStream(['{"suggestions":[', '{"action":"COLLECT_SAMPLES"}]}'], 0))

    model = ModelClient(config)
    model.client = AsyncOpenAI(api_key="test-only", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    flow.engine.model = model
    events = []
    async def sink(event: dict[str, object]) -> None:
        """Sink."""
        events.append(event)
    token = stream_sink.set(sink)
    try:
        result = await flow.run(request("分析统计", privacy=consent(config, "stats"),
            learningContext={"statistics": {"questionCount": 3, "correctCount": 1}},
            preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析统计", "reads": ["stats"]}))
        assert result["explanationMode"] == "ai" and "有效作答3次，正确1次" in result["answer"]
        assert len(sent) == model.budget.calls == 1 and sent[0]["stream"] is True
        assert not any(event["type"] == "delta" for event in events)
        assert "suggestions" not in result
    finally:
        stream_sink.reset(token)
        await model.close()
