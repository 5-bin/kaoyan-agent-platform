from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TaskType = Literal["KNOWLEDGE_QA", "SCHOOL_RECOMMEND", "PRACTICE_SUMMARY", "CHAT"]
PrivacyScope = Literal["wrong", "favorite", "stats", "profile", "document"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, hide_input_in_errors=True)


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
    privacy: PrivacyContext = Field(default_factory=PrivacyContext)

    @model_validator(mode="before")
    @classmethod
    def normalize_java_nulls(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for name, empty in (("messages", []), ("questions", []), ("profile", {}), ("preferences", {}), ("privacy", {})):
                if data.get(name) is None:
                    data[name] = empty
        return data

    @model_validator(mode="after")
    def task_fields(self):
        if self.taskType == "PRACTICE_SUMMARY" and not self.sessionId:
            raise ValueError("总结需要合法批次编号")
        if self.taskType != "PRACTICE_SUMMARY" and not self.userInput:
            raise ValueError("该任务需要非空 userInput")
        if self.taskType != "PRACTICE_SUMMARY" and (self.questions or self.sessionId):
            raise ValueError("仅练习总结接受作答快照")
        if self.taskType not in {"SCHOOL_RECOMMEND", "CHAT"} and self.preferences.model_fields_set:
            raise ValueError("该任务不接受择校偏好")
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


class Intent(StrictModel):
    intent: Literal["SCHOOL_RECOMMEND", "KNOWLEDGE_QA", "CHAT"]


class Answer(StrictModel):
    answer: str = Field(min_length=1, max_length=12000)
    sourceIds: list[str] = Field(min_length=1, max_length=5)


class Explanation(StrictModel):
    programId: str
    text: str = Field(min_length=1, max_length=2000)
    sourceIds: list[str] = Field(min_length=1, max_length=5)


class Explanations(StrictModel):
    explanations: list[Explanation] = Field(max_length=5)


class Summary(StrictModel):
    summary: str = Field(min_length=1, max_length=6000)


class ConversationConditions(Preferences):
    examYear: int | None = Field(default=None, ge=2000, le=2100)


class PersonalDocument(StrictModel):
    id: str = Field(min_length=1, max_length=36)
    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(max_length=40000)


class ConversationResolution(StrictModel):
    action: Literal["KNOWLEDGE_QA", "SCHOOL_RECOMMEND", "DOCUMENT_CREATE", "DOCUMENT_UPDATE", "CHAT", "LEARNING_ANALYSIS"]
    standaloneQuery: str = Field(min_length=1, max_length=8000)
    conditionPatch: ConversationConditions = Field(default_factory=ConversationConditions)
    clarification: str | None = Field(default=None, max_length=1000)
    reads: list[Literal["wrong", "favorite", "stats", "practice", "documents"]] = Field(default_factory=list, max_length=5)
    operation: Literal["NONE", "FAVORITE_ADD", "FAVORITE_REMOVE", "WRONG_REMOVE", "PRACTICE_CREATE"] = "NONE"
    target: Literal["selected", "visible", "wrong", "favorite", "normal"] = "selected"
    questionRefs: list[str] = Field(default_factory=list, max_length=50)
    subject: str | None = Field(default=None, max_length=50)
    difficulty: Literal["EASY", "MEDIUM", "HARD"] | None = None
    knowledgePoint: str | None = Field(default=None, min_length=1, max_length=255)
    count: int = Field(default=5, ge=1, le=50)
    from_: str | None = Field(default=None, alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$")
    to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    ordinal: int | None = Field(default=None, ge=1, le=50)

    @field_validator("questionRefs")
    @classmethod
    def question_aliases(cls, value):
        if any(not __import__("re").fullmatch(r"Q[1-9]\d{0,2}", ref) for ref in value):
            raise ValueError("题目引用必须为本轮别名")
        return list(dict.fromkeys(value))


class AssistantPageContext(StrictModel):
    page: Literal["wrong", "favorite", "stat", "documents", "practice", "notes"]
    subject: str | None = Field(default=None, max_length=50)
    from_: str | None = Field(default=None, alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$")
    to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class ConversationRequest(ChatRequest):
    conditions: ConversationConditions = Field(default_factory=ConversationConditions)
    document: PersonalDocument | None = None
    preparedPlan: ConversationResolution | None = None
    learningContext: dict | None = None
    pageContext: AssistantPageContext | None = None


class DocumentDraft(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=40000)
