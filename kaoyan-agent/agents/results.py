"""Typed execution metadata and explicit ownership of merged expert fields."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.errors import FallbackReason
from grounding import aggregate
from schemas import ExpertName, Reference, StrictModel, StudyPlan, TaskType


def check_fallback_reason(mode: str, reason: str | None) -> None:
    """Reject a fallback code on a layer that was not downgraded."""
    if reason is not None and mode != "fallback":
        raise ValueError("fallback_reason_without_fallback")


class ExpertResult(BaseModel):
    """Validate the common envelope; domain validators own the additional fields."""

    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)
    outcome: Literal["COMPLETED", "NEEDS_INPUT", "UNSUPPORTED"]
    answer: str = Field(max_length=20000)
    explanationMode: Literal["rules", "ai", "fallback"]
    fallbackReason: FallbackReason | None = None
    references: list[Reference] = Field(max_length=20)
    resolvedTaskType: TaskType
    releaseId: str
    clarificationOptions: list["ClarificationOption"] | None = Field(default=None, max_length=3)

    @model_validator(mode="after")
    def reason_only_for_fallback(self) -> "ExpertResult":
        """A fallback code describes a downgrade; it never accompanies rules or ai."""
        check_fallback_reason(self.explanationMode, self.fallbackReason)
        return self


class ClarificationOption(StrictModel):
    """A visible choice and its complete user message."""

    label: str = Field(min_length=1, max_length=60)
    reply: str = Field(min_length=1, max_length=2000)


class ExpertSection(StrictModel):
    """One planned expert's public completion state, without private input."""

    agent: ExpertName
    outcome: Literal["COMPLETED", "NEEDS_INPUT", "UNSUPPORTED"]
    explanationMode: Literal["rules", "ai", "fallback"]
    fallbackReason: FallbackReason | None = None
    notice: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def reason_only_for_fallback(self) -> "ExpertSection":
        """Keep the same pairing rule as the top-level result."""
        check_fallback_reason(self.explanationMode, self.fallbackReason)
        return self


@dataclass(frozen=True)
class StepContext:
    """Only an explicitly declared study-plan dependency may feed a note."""

    study_plan: StudyPlan | None = None


EXPERT_FIELDS: Mapping[ExpertName, tuple[str, ...]] = {
    "LEARNING": ("evidence", "retrievalStatus", "total", "readCount", "citationSupport"),
    "SCHOOL": (
        "candidates",
        "coverage",
        "excluded",
        "preferences",
        "profileSnapshot",
        "unverifiedCandidates",
        "citationSupport",
        "learningSnapshot",
        "resultSchemaVersion",
        "followUp",
        "admissionLinks",
    ),
    "KNOWLEDGE": (
        "recordId",
        "standardAnswer",
        "userAnswer",
        "questionVersion",
        "citationSupport",
        "followUp",
    ),
    "PRACTICE": (
        "operation",
        "questionRefs",
        "count",
        "target",
        "total",
        "readCount",
        "evidence",
        "retrievalStatus",
    ),
    "NOTE": ("documentProposal",),
    "STUDY_PLAN": ("studyPlan",),
}


def finalize_result(result: dict, release_id: str, task_type: TaskType) -> dict:
    """Attach and validate common metadata once at the native execution boundary."""
    result.setdefault("references", [])
    result.setdefault("explanationMode", "rules")
    result.setdefault("resolvedTaskType", task_type)
    result["releaseId"] = release_id
    ExpertResult.model_validate(result)
    return result


def contribute(result: dict, name: ExpertName, value: dict) -> None:
    """Merge only owned fields, union evidence, and reject silent overwrites."""
    for key in EXPERT_FIELDS[name]:
        if key not in value:
            continue
        if key == "citationSupport" and key in result:
            result[key] = aggregate([result[key], value[key]])
        elif key == "followUp":
            result[key] = list(dict.fromkeys(result.get(key, []) + value[key]))
        elif key == "evidence":
            existing = {item["ref"]: item for item in result.get(key, [])}
            for item in value[key]:
                if item["ref"] in existing and existing[item["ref"]] != item:
                    raise ValueError("conflicting_expert_evidence")
                existing[item["ref"]] = item
            result[key] = list(existing.values())
        elif key in result and result[key] != value[key]:
            raise ValueError("conflicting_expert_field")
        else:
            result[key] = value[key]
