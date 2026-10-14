"""请求/响应 schema。"""
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    taskId: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$", description="任务唯一 ID")
    userId: int = Field(..., gt=0, description="用户 ID")
    taskType: Literal["KNOWLEDGE_QA", "SCHOOL_RECOMMEND", "PRACTICE_SUMMARY", "CHAT"] = Field(..., description="KNOWLEDGE_QA / SCHOOL_RECOMMEND / PRACTICE_SUMMARY / CHAT")
    userInput: Optional[str] = Field(default=None, max_length=8000)
    sessionId: Optional[str] = Field(default=None, max_length=64)
    correctQuestionIds: Optional[list[int]] = Field(default_factory=list, max_length=100)
    wrongQuestionIds: Optional[list[int]] = Field(default_factory=list, max_length=100)
    messages: Optional[list[Any]] = Field(default_factory=list, max_length=100)
    profile: Optional[dict[str, Any]] = Field(default_factory=dict)

    def model_post_init(self, __ctx):
        # Spring 可能传 null，统一兜底为空容器
        if self.correctQuestionIds is None:
            self.correctQuestionIds = []
        if self.wrongQuestionIds is None:
            self.wrongQuestionIds = []
        if self.messages is None:
            self.messages = []
        if self.profile is None:
            self.profile = {}

    @model_validator(mode="after")
    def check_context(self):
        if self.taskType == "PRACTICE_SUMMARY":
            ids = self.correctQuestionIds + self.wrongQuestionIds
            if not self.sessionId or not self.sessionId.strip() or not ids:
                raise ValueError("总结需要已完成批次及有效作答")
            if any(i <= 0 for i in ids) or len(ids) != len(set(ids)):
                raise ValueError("题目编号必须为不重复的正数")
        elif not self.userInput or not self.userInput.strip():
            raise ValueError("任务输入不能为空")
        elif self.sessionId or self.correctQuestionIds or self.wrongQuestionIds:
            raise ValueError("当前任务不接受刷题上下文")
        return self


class ChatResponse(BaseModel):
    taskId: str
    status: Literal["SUCCESS", "FAILED"]
    result: Any = None
    references: list[Any] = Field(default_factory=list)
    errorMessage: Optional[str] = None
