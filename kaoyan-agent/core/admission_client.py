"""Independent admission-links MCP lifecycle and native HelloAgents adapter."""

import sys
from pathlib import Path

from mcp import StdioServerParameters, types

from admission_mcp_server import AdmissionConfig
from core.admission_contract import (
    SOURCE_FILE, TOOL_NAME, AdmissionLinksRegistry, AdmissionLinksResult,
)
from core.payload import checked_size
from core.mcp_runtime import OwnedMcpClient
from core.runtime import admission_budget
from schemas import AdmissionLinksQuery
from tools.registry import ValidatedTool


class McpAdmissionClient(OwnedMcpClient):
    """One application-owned stdio session over the local trusted registry only."""

    def __init__(self, source_path: Path = SOURCE_FILE) -> None:
        """Keep immutable local registry data; do not connect during import."""
        super().__init__(TOOL_NAME, 5.0)
        self.source_path = Path(source_path).resolve()
        self.registry = AdmissionLinksRegistry(self.source_path)

    def server_parameters(self) -> StdioServerParameters:
        """Pass only the explicit registry path, never dotenv or model credentials."""
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "admission_mcp_server"],
            cwd=str(Path(__file__).resolve().parents[1]),
            env={
                "KAOYAN_ADMISSION_CONFIG": AdmissionConfig(
                    sourcePath=self.source_path
                ).model_dump_json(),
                "PYTHON_DOTENV_DISABLED": "1",
                "PYTHONUNBUFFERED": "1",
            },
        )

    @staticmethod
    def validate_tools(discovered: types.ListToolsResult) -> None:
        """Reject extra tools, pagination, schema drift or external-read annotations."""
        if discovered.nextCursor is not None or len(discovered.tools) != 1:
            raise ValueError("ADMISSION_CATALOG_CHANGED")
        tool = discovered.tools[0]
        if tool.name != TOOL_NAME:
            raise ValueError("ADMISSION_CATALOG_CHANGED")
        if (
            tool.inputSchema != AdmissionLinksQuery.model_json_schema()
            or tool.outputSchema != AdmissionLinksResult.model_json_schema()
        ):
            raise ValueError("ADMISSION_SCHEMA_CHANGED")
        annotations = tool.annotations
        if (
            annotations is None
            or annotations.readOnlyHint is not True
            or annotations.idempotentHint is not True
            or annotations.openWorldHint is not False
            or annotations.destructiveHint is True
        ):
            raise ValueError("ADMISSION_SCHEMA_CHANGED")

    def validate_result(
        self, value: object, query: AdmissionLinksQuery
    ) -> AdmissionLinksResult:
        """Recheck exact fields and the full ordered URL list against local configuration."""
        checked_size(value)
        result = AdmissionLinksResult.model_validate(value)
        source = self.registry.sources.get(query.schoolCode)
        if source is None:
            raise ValueError("ADMISSION_SOURCE_UNKNOWN")
        expected = self.registry.get(query)
        if (
            result.schoolCode != query.schoolCode
            or result.schoolName != expected.schoolName
            or result.registeredYear != expected.registeredYear
            or result.entryUrls != expected.entryUrls
        ):
            raise ValueError("ADMISSION_LINKS_MISMATCH")
        return result

    async def check(self, **parameters: object) -> dict[str, object]:
        """Execute at most one local lookup per generation; never silently retry."""
        query = AdmissionLinksQuery.model_validate(parameters)
        self.registry.get(query)

        def decode(value: object) -> dict[str, object]:
            return self.validate_result(value, query).model_dump(mode="json")

        return await self.invoke(query.model_dump(), admission_budget.get(), decode)


class AdmissionLinksTool(ValidatedTool):
    """Use the pinned HelloAgents native adapter for the local registry lookup."""

    def __init__(self, client: McpAdmissionClient) -> None:
        """Register the exact typed parameter and validate decoded output again."""
        super().__init__(
            TOOL_NAME,
            "返回登记院校的招生官网链接与登记年份；不抓取网页、不判断最新招生内容。",
            AdmissionLinksQuery,
            client.check,
            lambda value: AdmissionLinksResult.model_validate(value),
        )
