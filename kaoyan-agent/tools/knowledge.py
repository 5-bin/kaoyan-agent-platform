"""Version-preserving knowledge search backed by the existing Retriever."""

from dataclasses import dataclass

from pydantic import Field

from retrieval import Document, Retriever
from schemas import StrictModel
from tools.registry import ValidatedTool


class SearchParameters(StrictModel):
    """Validated search scope; it cannot name a user or a database."""

    query: str = Field(min_length=1, max_length=8000)
    subject: str | None = None


@dataclass
class RetrievalHit:
    """Compatibility presentation wrapper, independent of LangChain Document."""

    page_content: str
    metadata: dict


class KnowledgeSearchTool(ValidatedTool):
    """Return only documents from the current immutable corpus version."""

    def __init__(self, backend: Retriever) -> None:
        """Bind the existing read-only retriever and validate restored documents."""

        def search(query: str, subject: str | None = None) -> list[Document]:
            return backend.search(query, "knowledge", 5, subject)

        def decode(values: list[dict]) -> list[RetrievalHit]:
            documents = [Document.model_validate(value) for value in values]
            return [RetrievalHit(item.content, {"chunk": item}) for item in documents]

        super().__init__(
            "retrieve_knowledge",
            "检索当前审核版本408资料，保留来源与原文定位。",
            SearchParameters,
            search,
            decode,
        )
