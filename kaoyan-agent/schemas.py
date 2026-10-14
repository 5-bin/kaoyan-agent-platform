"""请求/响应 schema。"""
from typing import Any, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    taskId: str = Field(..., description="任务唯一 ID")
    userId: int = Field(..., description="用户 ID")
    taskType: str = Field(..., description="KNOWLEDGE_QA / SCHOOL_RECOMMEND / PRACTICE_SUMMARY / CHAT")
    userInput: Optional[str] = None
    sessionId: Optional[str] = None
    correctQuestionIds: Optional[list[int]] = Field(default_factory=list)
    wrongQuestionIds: Optional[list[int]] = Field(default_factory=list)
    messages: Optional[list[Any]] = Field(default_factory=list)
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


class ChatResponse(BaseModel):
    taskId: str
    status: str = Field(..., description="SUCCESS / FAILED")
    result: Any = None
    references: list[Any] = Field(default_factory=list)
    errorMessage: Optional[str] = None
