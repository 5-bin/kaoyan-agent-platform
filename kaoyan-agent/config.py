from pathlib import Path
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlsplit, urlunsplit
from source_policy import DEFAULT_SOURCE_POLICY

ROOT = Path(__file__).resolve().parent


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
    MAX_MODEL_CALLS_PER_DAY: int = Field(default=100, ge=1)
    RAG_BACKEND: Literal["lexical", "bm25", "qdrant", "hybrid"] = "lexical"
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
