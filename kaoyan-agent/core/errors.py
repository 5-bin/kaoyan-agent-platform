"""Expected external failures that domain handlers may safely degrade."""

import re
from typing import Literal

from openai import APIError, APITimeoutError
from pydantic import ValidationError


class ModelUnavailable(RuntimeError):
    """The model is disabled or its provider is temporarily unavailable."""


class ModelBudgetExceeded(ModelUnavailable):
    """A request, phase or daily attempt allowance has been exhausted."""


class InvalidModelOutput(ValueError):
    """A provider result violates the declared domain/evidence contract."""


class ToolUnavailable(RuntimeError):
    """An expected read-only tool availability failure; never a programming bug."""


# SDK and Pydantic errors remain accepted for injected adapters and test doubles.
# Arbitrary ValueError/RuntimeError, TypeError and AttributeError must propagate.
MODEL_FAILURES = (
    APIError,
    ValidationError,
    TimeoutError,
    ModelUnavailable,
    InvalidModelOutput,
)


def failure_reason(error: BaseException) -> str:
    """Return a fixed diagnostic code; never model text, inputs or provider messages."""
    if isinstance(error, ValidationError):
        return ",".join(
            ".".join(str(part) for part in item["loc"]) + ":" + item["type"]
            for item in error.errors()[:3]
        )
    if isinstance(error, (InvalidModelOutput, ModelUnavailable)) and error.args:
        match = re.match(r"[a-z_]+", str(error.args[0]))
        return match.group(0) if match else ""
    return ""


FallbackReason = Literal[
    "TIMEOUT",
    "UNAVAILABLE",
    "BUDGET_EXHAUSTED",
    "INPUT_TOO_LONG",
    "INVALID_OUTPUT",
    "EVIDENCE_MISMATCH",
    "NUMBER_MISMATCH",
]
EVIDENCE_REASON = re.compile(r"evidence|source|support|citation")


def fallback_reason(error: BaseException) -> FallbackReason:
    """Map an expected model failure to the public fallback code shown to users."""
    if isinstance(error, (TimeoutError, APITimeoutError)):
        return "TIMEOUT"
    if isinstance(error, ModelBudgetExceeded):
        return "BUDGET_EXHAUSTED"
    if isinstance(error, ModelUnavailable):
        return "INPUT_TOO_LONG" if failure_reason(error) == "context_budget_exceeded" else "UNAVAILABLE"
    if isinstance(error, APIError):
        return "UNAVAILABLE"
    reason = failure_reason(error) if isinstance(error, InvalidModelOutput) else ""
    if reason.endswith("number_mismatch"):
        return "NUMBER_MISMATCH"
    if EVIDENCE_REASON.search(reason):
        return "EVIDENCE_MISMATCH"
    return "INVALID_OUTPUT"
