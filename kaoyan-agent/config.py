from pathlib import Path
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlsplit, urlunsplit
from source_policy import DEFAULT_SOURCE_POLICY

ROOT = Path(__file__).resolve().parent
# /conversation/plan waits for the parser plus room for its local fallback;
# Java's plan request gives up after 22 seconds (ConversationService).
PLAN_FALLBACK_SECONDS = 2
JAVA_PLAN_WAIT_SECONDS = 22


def provider_identifier(base_url):
    """Stable consent identity, never including URL credentials or query tokens."""
    try:
        endpoint = urlsplit(base_url)
        host = endpoint.hostname or ""
        if ":" in host:
            host = "[" + host + "]"
        if endpoint.port and endpoint.port != 443:
            host += ":" + str(endpoint.port)
        return (urlunsplit(("https", host, endpoint.path.rstrip("/"), "", ""))
                if endpoint.scheme == "https" and host else "unconfigured")
    except ValueError:
        return "unconfigured"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT.parent / ".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True)
    AGENT_INTERNAL_KEY: str = ""
    LLM_ENABLED: bool = False
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    LLM_MODEL_ROUTER: str = "glm-4-flash"
    LLM_MODEL_MAIN: str = "glm-4-plus"
    LLM_THINKING_MODE: Literal["default", "enabled", "disabled"] = "default"
    LLM_TIMEOUT: float = Field(default=20, ge=1, le=30)
    CONVERSATION_PARSE_TIMEOUT: float = Field(default=10, gt=0)
    # 2026-11-03: three serial expert attempts (measured 2–8.5 s each) need a longer stage.
    CONVERSATION_EXPERT_TIMEOUT: float = Field(default=28, gt=0)
    CONVERSATION_STEP_TIMEOUT: float = Field(default=12, gt=0)
    CONVERSATION_SUMMARY_TIMEOUT: float = Field(default=4, gt=0)
    AGENT_TASK_TIMEOUT: float = Field(default=42, gt=0, lt=48)
    MAX_MODEL_CALLS_PER_DAY: int = Field(default=100, ge=1)
    MODEL_CONTEXT_WINDOW: int = Field(default=32768, ge=1)
    MODEL_CONTEXT_RESERVE: int = Field(default=2048, ge=0)
    MODEL_INPUT_TOKENS: int = Field(default=12000, ge=1)
    MODEL_OUTPUT_TOKENS: int = Field(default=2200, ge=1)
    PLAN_INPUT_TOKENS: int = Field(default=8000, ge=1)
    PLAN_OUTPUT_TOKENS: int = Field(default=2048, ge=1)
    NOTE_INPUT_TOKENS: int = Field(default=20000, ge=1)
    NOTE_OUTPUT_TOKENS: int = Field(default=4096, ge=1)
    STUDY_OUTPUT_TOKENS: int = Field(default=8192, ge=1)
    RAG_BACKEND: Literal["lexical", "bm25", "qdrant", "hybrid"] = "lexical"
    ADMISSION_MCP_ENABLED: bool = False
    KNOWLEDGE_TOOL_TRANSPORT: Literal["local", "mcp_stdio"] = "local"
    RAG_DATA: Path = ROOT / "knowledge" / "corpus.json"
    RAG_SOURCE_POLICY_FILE: Path = DEFAULT_SOURCE_POLICY
    RAG_INDEX: Path = ROOT / ".cache" / "rag"
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    RAG_MIN_SCORE: float = Field(default=0.65, ge=0, le=1)
    QUESTION_INDEX: Path = ROOT / ".cache" / "questions"
    QUESTION_MODEL_CACHE: Path = ROOT / ".cache" / "embedding"
    QUESTION_MIN_SCORE: float = Field(default=0.75, ge=0, le=1)
    LOG_LEVEL: str = "INFO"

    @model_validator(mode="after")
    def validate_settings(self):
        phases = (self.CONVERSATION_PARSE_TIMEOUT + self.CONVERSATION_EXPERT_TIMEOUT
                  + self.CONVERSATION_SUMMARY_TIMEOUT)
        if phases > self.AGENT_TASK_TIMEOUT:
            raise ValueError("INVALID_PHASE_TIMEOUTS")
        if self.CONVERSATION_PARSE_TIMEOUT + PLAN_FALLBACK_SECONDS >= JAVA_PLAN_WAIT_SECONDS:
            raise ValueError("INVALID_PLAN_TIMEOUT")
        # One expert step may not consume the whole expert stage (measured
        # DeepSeek learning steps: 6.4–8+ s; study plan about 3.4 s).
        if self.CONVERSATION_STEP_TIMEOUT >= self.CONVERSATION_EXPERT_TIMEOUT:
            raise ValueError("INVALID_STEP_TIMEOUT")
        for input_limit, output_limit in (
            (self.MODEL_INPUT_TOKENS, self.MODEL_OUTPUT_TOKENS),
            (self.PLAN_INPUT_TOKENS, self.PLAN_OUTPUT_TOKENS),
            (self.NOTE_INPUT_TOKENS, self.NOTE_OUTPUT_TOKENS),
            (self.MODEL_INPUT_TOKENS, self.STUDY_OUTPUT_TOKENS),
        ):
            if input_limit + output_limit + self.MODEL_CONTEXT_RESERVE > self.MODEL_CONTEXT_WINDOW:
                raise ValueError("INVALID_MODEL_TOKEN_BUDGET")
        if not self.RAG_SOURCE_POLICY_FILE.is_absolute():
            raise ValueError("SOURCE_POLICY_INVALID")
        if len(self.AGENT_INTERNAL_KEY) < 16 or any(not 33 <= ord(c) <= 126 for c in self.AGENT_INTERNAL_KEY):
            raise ValueError("AGENT_INTERNAL_KEY 必须显式设置为至少16位ASCII字符")
        try:
            endpoint = urlsplit(self.LLM_BASE_URL)
            valid_endpoint = endpoint.scheme == "https" and bool(endpoint.hostname) and (endpoint.port is None or endpoint.port > 0)
        except ValueError:
            valid_endpoint = False
        if self.LLM_ENABLED and (not self.LLM_API_KEY or not valid_endpoint):
            raise ValueError("启用模型需要 API key 和 HTTPS 模型地址")
        return self
