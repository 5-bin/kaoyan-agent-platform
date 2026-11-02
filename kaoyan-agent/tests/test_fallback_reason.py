"""The public fallbackReason contract: fixed codes, paired only with fallback."""

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError
from pydantic import ValidationError

from agents.results import ExpertResult, ExpertSection
from conversation import ConversationWorkflow
from core.errors import InvalidModelOutput, ModelBudgetExceeded, ModelUnavailable, fallback_reason
from learning import LearningAnswer
from schemas import Answer
from tests.test_learning_privacy import engine, request

REQUEST = httpx.Request("POST", "https://provider.invalid/v1/chat/completions")


def validation_error() -> ValidationError:
    try:
        Answer.model_validate({})
    except ValidationError as error:
        return error
    raise AssertionError("expected a validation error")


@pytest.mark.parametrize(("error", "code"), [
    (TimeoutError(), "TIMEOUT"),
    (APITimeoutError(request=REQUEST), "TIMEOUT"),
    (APIConnectionError(request=REQUEST), "UNAVAILABLE"),
    (ModelUnavailable("model_disabled"), "UNAVAILABLE"),
    (ModelBudgetExceeded("request_model_limit"), "BUDGET_EXHAUSTED"),
    (ModelUnavailable("context_budget_exceeded"), "INPUT_TOO_LONG"),
    (InvalidModelOutput("learning_number_mismatch"), "NUMBER_MISMATCH"),
    (InvalidModelOutput("summary_number_mismatch"), "NUMBER_MISMATCH"),
    (InvalidModelOutput("unknown_evidence"), "EVIDENCE_MISMATCH"),
    (InvalidModelOutput("unsupported_summary"), "EVIDENCE_MISMATCH"),
    (InvalidModelOutput("invalid_model_json"), "INVALID_OUTPUT"),
    (InvalidModelOutput("model_output_truncated"), "INVALID_OUTPUT"),
    (InvalidModelOutput(), "INVALID_OUTPUT"),
])
def test_model_failures_map_to_fixed_public_codes(error, code):
    assert fallback_reason(error) == code


def test_schema_validation_errors_are_invalid_output():
    assert fallback_reason(validation_error()) == "INVALID_OUTPUT"


def envelope(**changes) -> dict:
    return {"outcome": "COMPLETED", "answer": "规则结果", "explanationMode": "fallback",
            "references": [], "resolvedTaskType": "CHAT", "releaseId": "rag-v1-test", **changes}


def test_reason_is_optional_and_only_allowed_on_fallback_layers():
    ExpertResult.model_validate(envelope())
    ExpertResult.model_validate(envelope(fallbackReason="TIMEOUT"))
    ExpertSection(agent="LEARNING", outcome="COMPLETED", explanationMode="fallback", fallbackReason="NUMBER_MISMATCH")
    for mode in ("rules", "ai"):
        with pytest.raises(ValidationError):
            ExpertResult.model_validate(envelope(explanationMode=mode, fallbackReason="TIMEOUT"))
        with pytest.raises(ValidationError):
            ExpertSection(agent="LEARNING", outcome="COMPLETED", explanationMode=mode, fallbackReason="TIMEOUT")
    with pytest.raises(ValidationError):
        ExpertResult.model_validate(envelope(fallbackReason="provider said: quota"))


@pytest.mark.asyncio
@pytest.mark.parametrize(("generated", "code"), [
    (LearningAnswer(answer="共练习24次。", evidenceRefs=[]), "NUMBER_MISMATCH"),
    (LearningAnswer(answer="样本不足。", evidenceRefs=["unknown"]), "EVIDENCE_MISMATCH"),
    (TimeoutError(), "TIMEOUT"),
])
async def test_learning_downgrade_names_its_reason(generated, code):
    service = engine()
    if isinstance(generated, BaseException):
        service.model.generate.side_effect = generated
    else:
        service.model.generate.return_value = generated
    req = request(
        privacy={"modelAllowed": True, "scopes": ["stats"]},
        learningContext={"statistics": {"questionCount": 3, "correctCount": 1}},
        preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析统计", "reads": ["stats"]},
    )
    result = await ConversationWorkflow(service).run(req)
    assert result["explanationMode"] == "fallback"
    assert result["fallbackReason"] == code


@pytest.mark.asyncio
async def test_successful_and_rule_results_carry_no_reason():
    service = engine()
    service.model.generate.return_value = LearningAnswer(suggestions=[{"action": "COLLECT_SAMPLES"}])
    req = request(
        privacy={"modelAllowed": True, "scopes": ["stats"]},
        learningContext={"statistics": {"questionCount": 3, "correctCount": 1}},
        preparedPlan={"action": "LEARNING_ANALYSIS", "standaloneQuery": "分析统计", "reads": ["stats"]},
    )
    assert "fallbackReason" not in await ConversationWorkflow(service).run(req)
    req.privacy.modelAllowed = False
    assert "fallbackReason" not in await ConversationWorkflow(service).run(req)


@pytest.mark.asyncio
async def test_compound_sections_keep_each_experts_reason():
    service = engine()

    async def generate(prompt, payload, schema, **kwargs):
        if schema is LearningAnswer:
            return LearningAnswer(answer="共练习24次。", evidenceRefs=[])
        raise TimeoutError()

    service.model.generate.side_effect = generate
    req = request(
        userInput="分析学情并解释进程与线程",
        privacy={"modelAllowed": True, "scopes": ["stats"]},
        learningContext={"statistics": {"questionCount": 3, "correctCount": 1}},
        preparedPlan={
            "action": "MULTI_AGENT", "standaloneQuery": "分析学情并解释进程与线程", "planVersion": 2,
            "steps": [{"agent": "LEARNING", "dependsOn": []}, {"agent": "KNOWLEDGE", "dependsOn": []}],
            "reads": ["stats"],
        },
    )
    result = await ConversationWorkflow(service).run(req)
    assert [(item["agent"], item["explanationMode"], item.get("fallbackReason")) for item in result["sections"]] == [
        ("LEARNING", "fallback", "NUMBER_MISMATCH"), ("KNOWLEDGE", "fallback", "TIMEOUT"),
    ]
    # The combined layer stays rules and never inherits an expert's code.
    assert result["explanationMode"] == "rules" and "fallbackReason" not in result
