from pathlib import Path
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT.parent / ".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True)
    AGENT_INTERNAL_KEY: str = ""
    LLM_ENABLED: bool = False
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    LLM_MODEL_ROUTER: str = "glm-4-flash"
    LLM_MODEL_MAIN: str = "glm-4-plus"
    LLM_TIMEOUT: float = Field(default=20, ge=1, le=30)
    MAX_MODEL_CALLS_PER_DAY: int = Field(default=100, ge=1)
    RAG_BACKEND: Literal["lexical", "qdrant"] = "lexical"
    RAG_DATA: Path = ROOT / "knowledge" / "corpus.json"
    RAG_INDEX: Path = ROOT / ".cache" / "rag"
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    RAG_MIN_SCORE: float = Field(default=0.65, ge=0, le=1)
    LOG_LEVEL: str = "INFO"

    @model_validator(mode="after")
    def validate_settings(self):
        if len(self.AGENT_INTERNAL_KEY) < 16 or any(not 33 <= ord(c) <= 126 for c in self.AGENT_INTERNAL_KEY):
            raise ValueError("AGENT_INTERNAL_KEY 必须显式设置为至少16位ASCII字符")
        if self.LLM_ENABLED and (not self.LLM_API_KEY or not self.LLM_BASE_URL.startswith("https://")):
            raise ValueError("启用模型需要 API key 和 HTTPS 模型地址")
        return self
