"""Typed, version-preserving wire contract for the sole read-only MCP tool."""

from pathlib import Path
from typing import Literal

from pydantic import Field

from config import Settings
from core.payload import checked_size
from retrieval import Document
from schemas import StrictModel
from tools.knowledge import SearchParameters

TOOL_NAME = "retrieve_knowledge"
CALL_TIMEOUT = 5.0


class RetrievalConfig(StrictModel):
    """Explicit child configuration; never reads dotenv or business credentials."""

    RAG_DATA: Path
    RAG_SOURCE_POLICY_FILE: Path
    RAG_BACKEND: Literal["lexical", "bm25", "qdrant", "hybrid"]
    RAG_INDEX: Path
    QDRANT_URL: str
    QDRANT_API_KEY: str
    EMBEDDING_MODEL: str
    QUESTION_MODEL_CACHE: Path
    RAG_MIN_SCORE: float = Field(ge=0, le=1)

    @classmethod
    def from_settings(cls, settings: Settings) -> "RetrievalConfig":
        """Copy only retrieval fields and resolve paths before changing child cwd."""
        values = {
            name: getattr(settings, name)
            for name in cls.model_fields
        }
        for name in ("RAG_DATA", "RAG_SOURCE_POLICY_FILE", "RAG_INDEX", "QUESTION_MODEL_CACHE"):
            values[name] = Path(values[name]).resolve()
        return cls.model_validate(values)


class KnowledgeResult(StrictModel):
    """Structured evidence response; an empty match is a valid successful result."""

    releaseId: str = Field(pattern=r"^rag-v1-[a-f0-9]{16}$")
    retrievalBackend: Literal["lexical", "bm25", "qdrant", "hybrid"]
    documents: list[Document] = Field(max_length=5)


def input_schema() -> dict[str, object]:
    """Return the existing Pydantic tool parameters as a complete JSON Schema."""
    return SearchParameters.model_json_schema()


def output_schema() -> dict[str, object]:
    """Return the exact versioned evidence schema used by both protocol peers."""
    return KnowledgeResult.model_json_schema()
