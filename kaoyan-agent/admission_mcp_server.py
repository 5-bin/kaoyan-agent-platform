"""Local-only stdio admission service exposing registered links and nothing else."""

import asyncio
import logging
import os
from pathlib import Path

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from core.admission_contract import (
    SOURCE_FILE, TOOL_NAME, AdmissionLinksRegistry, AdmissionLinksResult,
)
from core.payload import checked_size
from schemas import AdmissionLinksQuery, StrictModel


class AdmissionConfig(StrictModel):
    """Explicit trusted registry path; no corpus, credentials or diagnostic sink."""

    sourcePath: Path = SOURCE_FILE


async def serve(
    config: AdmissionConfig, registry: AdmissionLinksRegistry | None = None
) -> None:
    """Expose exactly one local lookup; no index, network or model client is created."""
    registry = registry or AdmissionLinksRegistry(config.sourcePath)
    server = Server("kaoyan-admission-links")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        """Publish stable local schemas with closed-world, read-only annotations."""
        return [types.Tool(
            name=TOOL_NAME,
            description="返回登记院校的招生官网链接与登记年份；不抓取网页、不判断最新招生内容。",
            inputSchema=AdmissionLinksQuery.model_json_schema(),
            outputSchema=AdmissionLinksResult.model_json_schema(),
            annotations=types.ToolAnnotations(
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )]

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
        """Validate every argument locally, reject unknown codes, and bound the result."""
        if name != TOOL_NAME:
            raise ValueError("ADMISSION_UNKNOWN_TOOL")
        query = AdmissionLinksQuery.model_validate(arguments)
        value = registry.get(query).model_dump(mode="json")
        checked_size(value)
        return value

    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


def main() -> None:
    """Read only the explicit child registry configuration; stdout is protocol-only."""
    logging.getLogger("mcp").addHandler(logging.NullHandler())
    logging.getLogger("mcp").propagate = False
    try:
        config = AdmissionConfig.model_validate_json(
            os.environ.get("KAOYAN_ADMISSION_CONFIG", "")
        )
        asyncio.run(serve(config))
    except Exception as error:
        logging.getLogger(__name__).error(
            "admissionServerFailure=%s", type(error).__name__
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
