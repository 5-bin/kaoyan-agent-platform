"""Application-owned asynchronous MCP session and validated HelloAgents adapter."""

import sys
from pathlib import Path

from mcp import StdioServerParameters, types

from config import Settings
from core.mcp_contract import (
    CALL_TIMEOUT,
    TOOL_NAME,
    KnowledgeResult,
    RetrievalConfig,
    checked_size,
    input_schema,
    output_schema,
)
from core.mcp_runtime import OwnedMcpClient
from core.runtime import retrieval_budget
from retrieval import Corpus, Document
from source_policy import ReferenceSourcePolicy
from tools.knowledge import RetrievalHit, SearchParameters
from tools.registry import ValidatedTool


class McpKnowledgeClient(OwnedMcpClient):
    """One trusted stdio child/session per app; requests carry only search data."""

    def __init__(self, settings: Settings, corpus: Corpus) -> None:
        """Bind expected immutable evidence; do not spawn or connect on import."""
        super().__init__(TOOL_NAME, CALL_TIMEOUT)
        self.config = RetrievalConfig.from_settings(settings)
        self.corpus = corpus
        self.policy = ReferenceSourcePolicy(settings.RAG_SOURCE_POLICY_FILE)

    def server_parameters(self) -> StdioServerParameters:
        """Use a fixed interpreter/module and an explicit retrieval-only child env."""
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server"],
            cwd=str(Path(__file__).resolve().parents[1]),
            env={
                "KAOYAN_MCP_RETRIEVAL_CONFIG": self.config.model_dump_json(),
                "PYTHON_DOTENV_DISABLED": "1",
                "PYTHONUNBUFFERED": "1",
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
            },
        )

    @staticmethod
    def validate_tools(discovered: types.ListToolsResult) -> None:
        """Reject catalog drift rather than automatically exposing new tools."""
        if discovered.nextCursor is not None or len(discovered.tools) != 1:
            raise ValueError("MCP_TOOL_CATALOG_CHANGED")
        tool = discovered.tools[0]
        if tool.name != TOOL_NAME:
            raise ValueError("MCP_TOOL_CATALOG_CHANGED")
        if (
            tool.inputSchema != input_schema()
            or tool.outputSchema != output_schema()
        ):
            raise ValueError("MCP_TOOL_SCHEMA_CHANGED")

    def validate_result(self, value: object) -> list[Document]:
        """Check bounds, version, provenance and exact current corpus membership."""
        checked_size(value)
        result = KnowledgeResult.model_validate(value)
        if (
            result.releaseId != self.corpus.release_id
            or result.retrievalBackend != self.config.RAG_BACKEND
        ):
            raise ValueError("MCP_EVIDENCE_VERSION_MISMATCH")
        seen: set[str] = set()
        for document in result.documents:
            self.policy.validate_url(document.url)
            expected = self.corpus.chunk_by_id.get(document.id)
            base_id = document.id.split("#", 1)[0]
            if (
                document.domain != "knowledge"
                or expected is None
                or document != expected
                or base_id in seen
            ):
                raise ValueError("MCP_EVIDENCE_NOT_AUTHORIZED")
            seen.add(base_id)
        return result.documents

    async def search(self, query: str, subject: str | None = None) -> list[Document]:
        """Make one bounded attempt; cancellation never replaces the shared session."""
        parameters = SearchParameters(query=query, subject=subject)

        def decode(value: object) -> list[Document]:
            documents = self.validate_result(value)
            if subject and any(document.subject != subject for document in documents):
                raise ValueError("MCP_EVIDENCE_SCOPE_MISMATCH")
            return documents

        return await self.invoke(parameters.model_dump(), retrieval_budget.get(), decode)


class McpKnowledgeSearchTool(ValidatedTool):
    """Native HelloAgents tool preserving the existing retrieval-hit contract."""

    def __init__(self, client: McpKnowledgeClient) -> None:
        """Inject the application session without altering expert call sites."""
        def decode(values: list[dict[str, object]]) -> list[RetrievalHit]:
            """Restore only already-validated domain evidence from native tool JSON."""
            documents = [Document.model_validate(value) for value in values]
            return [RetrievalHit(item.content, {"chunk": item}) for item in documents]

        super().__init__(
            TOOL_NAME,
            "检索当前审核版本408资料，保留来源与原文定位。",
            SearchParameters,
            client.search,
            decode,
        )
