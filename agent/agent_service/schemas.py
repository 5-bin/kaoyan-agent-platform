from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TaskType = Literal["knowledge_qa", "school_recommendation", "wrong_question_tutor"]
Subject = Literal["data_structure", "computer_organization", "operating_system", "computer_network"]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class KnowledgeContext(StrictModel):
    subject: Subject | None = None

class ProfileSnapshot(StrictModel):
    examYear: int | None = Field(default=None, ge=2000, le=2100)
    targetMajorCodes: list[str] = Field(default_factory=list, max_length=30)
    degreeType: Literal["academic", "professional"] | None = None
    regions: list[str] = Field(default_factory=list, max_length=30)
    regionConstraint: Literal["required", "preferred"] | None = None
    studyMode: str | None = None
    examSubjects: list[str] = Field(default_factory=list)
    foundation: str | None = None
    estimatedScores: dict[str, int] = Field(default_factory=dict)

class RecommendationPreferences(StrictModel):
    regions: list[str] = Field(default_factory=list, max_length=30)
    regionConstraint: Literal["required", "preferred"] | None = None
    studyMode: str | None = None
    examSubjects: list[str] = Field(default_factory=list)

class AdmissionCandidate(StrictModel):
    programId: UUID
    title: str
    examYear: int = Field(ge=2000, le=2100)
    sourceIds: list[str] = Field(default_factory=list)

class SchoolContext(StrictModel):
    profileSnapshot: ProfileSnapshot | None = None
    preferences: RecommendationPreferences = Field(default_factory=RecommendationPreferences)
    candidates: list[AdmissionCandidate] = Field(default_factory=list)

class QuestionSnapshot(StrictModel):
    stem: str
    options: dict[str, str]
    explanation: str
    sourceIds: list[str] = Field(default_factory=list)

class QuestionCandidate(StrictModel):
    questionId: UUID
    knowledgePointIds: list[str] = Field(default_factory=list)

class WrongQuestionContext(StrictModel):
    attemptId: UUID | None = None
    questionId: UUID | None = None
    questionVersionId: UUID | None = None
    selectedOption: str | None = None
    correctOption: str | None = None
    correct: bool | None = None
    questionSnapshot: QuestionSnapshot | None = None
    subject: Subject | None = None
    knowledgePointIds: list[str] = Field(default_factory=list)
    availableQuestions: list[QuestionCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_answer(self):
        if self.questionSnapshot and self.correctOption not in self.questionSnapshot.options:
            raise ValueError("标准选项必须存在于题目快照中")
        return self

CONTEXT_TYPES = {"knowledge_qa": KnowledgeContext, "school_recommendation": SchoolContext,
                 "wrong_question_tutor": WrongQuestionContext}

class RunRequest(StrictModel):
    taskId: UUID
    input: str = Field(min_length=1, max_length=8000)
    taskType: TaskType = "knowledge_qa"
    releaseId: Literal["demo-408-v1"] = "demo-408-v1"
    context: KnowledgeContext | SchoolContext | WrongQuestionContext = Field(default_factory=KnowledgeContext)

    @model_validator(mode="before")
    @classmethod
    def typed_context(cls, data):
        if isinstance(data, dict):
            context_type = CONTEXT_TYPES.get(data.get("taskType", "knowledge_qa"))
            if context_type:
                data = dict(data)
                data["context"] = context_type.model_validate(data.get("context", {}))
        return data

    @field_validator("input")
    @classmethod
    def trim_input(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("任务输入不能为空")
        return value


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    url: str
    locator: str
    version: str
    excerpt: str
    retrievedAt: str


class RunResult(BaseModel):
    taskId: str
    status: Literal["completed", "needs_input", "unsupported", "failed"]
    mode: Literal["demo", "model"]
    answer: str = Field(max_length=20000)
    steps: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    followUp: list[str] = Field(default_factory=list)
    latencyMs: int = Field(default=0, ge=0)
    releaseId: str = "demo-408-v1"
    data: dict = Field(default_factory=dict)


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "needs_input", "unsupported"]
    answer: str = Field(min_length=1, max_length=20000)
    steps: list[str] = Field(max_length=10)
    sourceIds: list[str] = Field(max_length=10)
    followUp: list[str] = Field(max_length=5)
