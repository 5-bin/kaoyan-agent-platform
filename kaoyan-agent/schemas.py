from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TaskType = Literal[
    "KNOWLEDGE_QA",
    "SCHOOL_RECOMMEND",
    "PRACTICE_SUMMARY",
    "CHAT",
    "WRONG_QUESTION_TUTOR",
]
PrivacyScope = Literal["wrong", "favorite", "stats", "profile", "document"]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, hide_input_in_errors=True
    )


class PrivacyContext(StrictModel):
    modelAllowed: bool = False
    scopes: list[PrivacyScope] = Field(default_factory=list, max_length=5)
    version: int = Field(default=0, ge=0)
    provider: str | None = Field(default=None, max_length=500)


class Message(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)
    # Missing metadata denotes legacy history whose sensitivity is unknown.
    scopes: list[PrivacyScope] | None = Field(default=None, max_length=5)


class Profile(StrictModel):
    targetSchool: str | None = Field(default=None, max_length=255)
    targetMajor: str | None = Field(default=None, max_length=255)
    examYear: int | None = Field(default=None, ge=2000, le=2100)
    background: str | None = Field(default=None, max_length=4000)


class Preferences(StrictModel):
    majorCodes: list[str] | None = Field(default=None, max_length=10)
    degreeType: Literal["academic", "professional"] | None = None
    regions: list[str] | None = Field(default=None, max_length=30)
    regionConstraint: Literal["required", "preferred"] = "preferred"
    studyMode: Literal["full_time", "part_time"] | None = None
    examSubjects: list[str] | None = Field(default=None, max_length=4)
    explainWithAi: bool = True

    @field_validator("majorCodes")
    @classmethod
    def majors(cls, value):
        if value is not None and any(len(v) != 6 or not v.isdigit() for v in value):
            raise ValueError("专业使用六位代码")
        return value


class QuestionSnapshot(StrictModel):
    id: int = Field(gt=0)
    version: int = Field(default=1, ge=1)
    subject: str = Field(max_length=50)
    knowledgePoint: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1, max_length=10000)
    answer: str = Field(min_length=1, max_length=10)
    analysis: str | None = Field(default=None, max_length=10000)
    correct: bool


class LearningSnapshot(StrictModel):
    profileRevision: int = Field(ge=0)
    referenceScore: float | None = Field(
        default=None, ge=0, le=150, allow_inf_nan=False
    )
    coverage: float = Field(ge=0, le=1, allow_inf_nan=False)
    sufficient: bool = False
    blueprintVersion: str = Field(min_length=1, max_length=100)
    calibrated: Literal[False] = False


class TutoringAttempt(StrictModel):
    """Java-authorized, already graded snapshot; never supplied by the browser."""

    recordId: int = Field(gt=0, strict=True)
    id: int = Field(gt=0, strict=True)
    version: int = Field(ge=1, strict=True)
    subject: str = Field(min_length=1, max_length=50)
    knowledgePoint: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1, max_length=10000)
    optionA: str = Field(min_length=1, max_length=10000)
    optionB: str = Field(min_length=1, max_length=10000)
    optionC: str = Field(min_length=1, max_length=10000)
    optionD: str = Field(min_length=1, max_length=10000)
    answer: Literal["A", "B", "C", "D"]
    userAnswer: Literal["A", "B", "C", "D"]
    analysis: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def wrong_only(self) -> "TutoringAttempt":
        """Reject snapshots that contradict the wrong-answer eligibility rule."""
        if self.answer == self.userAnswer:
            raise ValueError("辅导仅接受已判错作答")
        return self


class TutorExplanation(StrictModel):
    """Bounded model prose with an independently checked standard answer."""

    explanation: str = Field(min_length=1, max_length=4000)
    standardAnswer: Literal["A", "B", "C", "D"]


class ChatRequest(StrictModel):
    taskId: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    userId: int = Field(gt=0)
    quotaExempt: bool = False
    taskType: TaskType
    userInput: str | None = Field(default=None, max_length=8000)
    sessionId: str | None = Field(default=None, max_length=64)
    messages: list[Message] = Field(default_factory=list, max_length=6)
    profile: Profile = Field(default_factory=Profile)
    preferences: Preferences = Field(default_factory=Preferences)
    questions: list[QuestionSnapshot] = Field(default_factory=list, max_length=50)
    attempt: TutoringAttempt | None = None
    privacy: PrivacyContext = Field(default_factory=PrivacyContext)
    learningSnapshot: LearningSnapshot | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_java_nulls(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for name, empty in (
                ("messages", []),
                ("questions", []),
                ("profile", {}),
                ("preferences", {}),
                ("privacy", {}),
            ):
                if data.get(name) is None:
                    data[name] = empty
        return data

    @model_validator(mode="after")
    def task_fields(self):
        if self.taskType == "WRONG_QUESTION_TUTOR":
            if self.attempt is None or not self.userInput or len(self.userInput) > 2000:
                raise ValueError("辅导需要授权作答及1—2000字符问题")
        elif self.attempt is not None and not (
            isinstance(self, ConversationRequest) and self.taskType == "CHAT"
        ):
            raise ValueError("仅错题辅导接受 attempt")
        if self.taskType == "PRACTICE_SUMMARY" and not self.sessionId:
            raise ValueError("总结需要合法批次编号")
        if self.taskType != "PRACTICE_SUMMARY" and not self.userInput:
            raise ValueError("该任务需要非空 userInput")
        if self.taskType != "PRACTICE_SUMMARY" and (self.questions or self.sessionId):
            raise ValueError("仅练习总结接受作答快照")
        if (
            self.taskType not in {"SCHOOL_RECOMMEND", "CHAT"}
            and self.preferences.model_fields_set
        ):
            raise ValueError("该任务不接受择校偏好")
        if self.learningSnapshot is not None and self.taskType != "SCHOOL_RECOMMEND":
            raise ValueError("仅择校接受学情聚合快照")
        if len({q.id for q in self.questions}) != len(self.questions):
            raise ValueError("题目快照不能重复")
        return self


class Reference(StrictModel):
    id: str
    title: str
    url: str
    locator: str
    version: str
    retrievedAt: str
    excerpt: str


class ChatResponse(StrictModel):
    taskId: str
    status: Literal["SUCCESS", "FAILED"]
    result: dict = Field(default_factory=dict)
    references: list[Reference] = Field(default_factory=list, max_length=20)
    releaseId: str = ""
    errorMessage: str | None = None


class Claim(StrictModel):
    text: str = Field(min_length=1, max_length=1000)
    sourceIds: list[str] = Field(min_length=1, max_length=5)


class Answer(StrictModel):
    answer: str = Field(min_length=1, max_length=12000)
    sourceIds: list[str] = Field(min_length=1, max_length=5)
    # Optional for older callers and fake models; when present each claim is
    # checked against only its own cited excerpts.
    claims: list[Claim] = Field(default_factory=list, max_length=10)


class Explanation(StrictModel):
    programId: str
    text: str = Field(min_length=1, max_length=2000)
    sourceIds: list[str] = Field(min_length=1, max_length=5)


class Explanations(StrictModel):
    explanations: list[Explanation] = Field(max_length=5)


class Summary(StrictModel):
    # Providers (e.g. DeepSeek) add keys such as "additional"; only the
    # validated summary prose is used, so unknown keys are dropped, not shown.
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True, hide_input_in_errors=True)
    summary: str = Field(min_length=1, max_length=6000)


class ConversationConditions(Preferences):
    examYear: int | None = Field(default=None, ge=2000, le=2100)


class PersonalDocument(StrictModel):
    id: str = Field(min_length=1, max_length=36)
    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(max_length=40000)


ExpertName = Literal[
    "LEARNING", "SCHOOL", "KNOWLEDGE", "PRACTICE", "NOTE", "STUDY_PLAN"
]


class ExpertStep(StrictModel):
    """A bounded data dependency, never arbitrary executable model output."""

    agent: ExpertName
    dependsOn: list[ExpertName] = Field(default_factory=list, max_length=5)


class AdmissionLinksQuery(StrictModel):
    """Only a registered school code; URLs and personal context are forbidden."""

    schoolCode: str = Field(
        min_length=2,
        max_length=8,
        pattern=r"^[a-z]{2,8}$",
        description="config/admission-sources.json 中的登记院校代码",
    )


class SchoolLookupQuery(StrictModel):
    """Public catalog filters, verified again against the current query by Java."""

    schoolName: str = Field(min_length=4, max_length=255)
    year: int | None = Field(default=None, ge=2000, le=2100)
    majorCode: str | None = Field(default=None, pattern=r"^\d{6}$")


class ConversationResolution(StrictModel):
    action: Literal[
        "SCHOOL_LOOKUP",
        "ADMISSION_LINKS",
        "KNOWLEDGE_QA",
        "SCHOOL_RECOMMEND",
        "DOCUMENT_CREATE",
        "DOCUMENT_UPDATE",
        "CHAT",
        "LEARNING_ANALYSIS",
        "STUDY_PLAN",
        "MULTI_AGENT",
        "WRONG_QUESTION_TUTOR",
    ]
    admissionLinks: AdmissionLinksQuery | None = None
    schoolLookup: SchoolLookupQuery | None = None
    standaloneQuery: str = Field(min_length=1, max_length=8000)
    conditionPatch: ConversationConditions = Field(
        default_factory=ConversationConditions
    )
    clarification: str | None = Field(default=None, max_length=1000)
    reads: list[
        Literal["wrong", "favorite", "stats", "practice", "documents", "questions"]
    ] = Field(default_factory=list, max_length=6)
    operation: Literal[
        "NONE", "FAVORITE_ADD", "FAVORITE_REMOVE", "WRONG_REMOVE", "PRACTICE_CREATE"
    ] = "NONE"
    target: Literal["selected", "visible", "wrong", "favorite", "normal"] = "selected"
    questionRefs: list[str] = Field(default_factory=list, max_length=50)
    subject: str | None = Field(default=None, max_length=50)
    difficulty: Literal["EASY", "MEDIUM", "HARD"] | None = None
    knowledgePoint: str | None = Field(default=None, min_length=1, max_length=255)
    count: int = Field(default=5, ge=1, le=50)
    from_: str | None = Field(
        default=None, alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    ordinal: int | None = Field(default=None, ge=1, le=50)
    planVersion: Literal[1, 2] = 1
    steps: list[ExpertStep] = Field(default_factory=list, max_length=6)
    modelCallsUsed: int = Field(default=0, ge=0, le=1)
    studyDays: int = Field(default=7, ge=1, le=30)

    @model_validator(mode="after")
    def ordered_steps(self) -> "ConversationResolution":
        """Require unique experts and only backward dependencies (a DAG)."""
        seen = set()
        for step in self.steps:
            if (
                step.agent in seen
                or len(step.dependsOn) != len(set(step.dependsOn))
                or not set(step.dependsOn) <= seen
            ):
                raise ValueError("invalid_expert_dependencies")
            seen.add(step.agent)
        if self.steps and self.planVersion != 2:
            raise ValueError("steps_require_plan_version_2")
        if self.action in {"MULTI_AGENT", "STUDY_PLAN"} and (
            not self.steps or self.planVersion != 2
        ):
            raise ValueError("missing_expert_steps")
        if self.action in {"ADMISSION_LINKS", "SCHOOL_LOOKUP"} and self.steps:
            raise ValueError("admission_links_have_no_steps")
        return self

    @field_validator("questionRefs")
    @classmethod
    def question_aliases(cls, value):
        if any(not __import__("re").fullmatch(r"Q[1-9]\d{0,2}", ref) for ref in value):
            raise ValueError("题目引用必须为本轮别名")
        return list(dict.fromkeys(value))


class AssistantPageContext(StrictModel):
    page: Literal["wrong", "favorite", "stat", "documents", "practice", "notes"]
    subject: str | None = Field(default=None, max_length=50)
    from_: str | None = Field(
        default=None, alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class ConversationRequest(ChatRequest):
    conditions: ConversationConditions = Field(default_factory=ConversationConditions)
    document: PersonalDocument | None = None
    preparedPlan: ConversationResolution | None = None
    learningContext: dict | None = None
    pageContext: AssistantPageContext | None = None

    @model_validator(mode="before")
    @classmethod
    def discard_legacy_admission_plan(cls, data: object) -> object:
        """Never revive an older prepared crawler plan; resolve the current text afresh."""
        if isinstance(data, dict) and isinstance(data.get("preparedPlan"), dict):
            plan = data["preparedPlan"]
            if plan.get("action") == "ADMISSION_CHECK" or plan.get("admissionCheck") is not None:
                data = dict(data)
                query = plan.get("standaloneQuery")
                data["preparedPlan"] = {
                    "action": "CHAT",
                    "standaloneQuery": query if isinstance(query, str) and query else "招生官网链接查询",
                    "clarification": "旧版招生核验计划已停用，请重新发送明确的招生官网链接查询。",
                }
        return data


class DocumentDraft(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=40000)


class StudyDay(StrictModel):
    """Relative days avoid inventing dates or available study hours."""

    day: int = Field(ge=1, le=30)
    topic: str = Field(min_length=1, max_length=255)
    tasks: list[str] = Field(min_length=1, max_length=5)


class StudyPlan(StrictModel):
    """A draft plan stored in the existing task result JSON."""

    days: list[StudyDay] = Field(min_length=1, max_length=30)
    basis: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def day_order(self) -> "StudyPlan":
        """Do not accept repeated or skipped day indexes."""
        if [day.day for day in self.days] != list(range(1, len(self.days) + 1)):
            raise ValueError("invalid_study_day_order")
        if any(
            len(task) > 1000 or not task.strip()
            for day in self.days
            for task in day.tasks
        ):
            raise ValueError("invalid_study_task")
        if any(len(item) > 1000 for item in self.basis):
            raise ValueError("invalid_study_basis")
        return self


class CombinedAnswer(StrictModel):
    """Only final prose is synthesized; expert structures remain authoritative."""

    answer: str = Field(min_length=1, max_length=12000)
    sourceIds: list[str] = Field(default_factory=list, max_length=20)
