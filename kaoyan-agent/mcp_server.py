"""Fixed stdio entrypoint exposing only the existing reviewed knowledge search."""

import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from pydantic import ValidationError

from core.mcp_contract import (
    TOOL_NAME,
    KnowledgeResult,
    RetrievalConfig,
    checked_size,
    input_schema,
    output_schema,
)
from retrieval import Corpus, Retriever
from tools.knowledge import KnowledgeSearchTool, SearchParameters


async def serve(config: RetrievalConfig) -> None:
    """Serve reviewed evidence; close workers before closing their shared index."""
    corpus = Corpus(config.RAG_DATA, config.RAG_SOURCE_POLICY_FILE)
    retriever = Retriever(config, corpus, local_files_only=True)
    tool = KnowledgeSearchTool(retriever)
    server = Server("kaoyan-reviewed-knowledge")
    workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mcp-retrieval")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        """Advertise exactly one immutable, non-writing domain capability."""
        return [types.Tool(
            name=TOOL_NAME,
            description=tool.description,
            inputSchema=input_schema(),
            outputSchema=output_schema(),
            annotations=types.ToolAnnotations(
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )]

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
        """Validate input before scheduling bounded synchronous read-only work."""
        if name != TOOL_NAME:
            raise ValueError("MCP_UNKNOWN_TOOL")
        try:
            parameters = SearchParameters.model_validate(arguments)
        except ValidationError:
            raise ValueError("MCP_INVALID_ARGUMENTS") from None
        try:
            # Cancelling a queued Future stops it; an already-running read may
            # finish in its worker. The pool still caps live reads at two.
            encoded = await asyncio.get_running_loop().run_in_executor(
                workers, tool.run, parameters.model_dump()
            )
            result = KnowledgeResult(
                releaseId=corpus.release_id,
                retrievalBackend=config.RAG_BACKEND,
                documents=json.loads(encoded),
            ).model_dump(mode="json")
            checked_size(result)
            return result
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logging.getLogger(__name__).warning(
                "mcpRetrievalFailure=%s", type(error).__name__
            )
            raise ValueError("MCP_RETRIEVAL_FAILED") from None

    try:
        async with stdio_server() as (reader, writer):
            await server.run(reader, writer, server.create_initialization_options())
    finally:
        await asyncio.to_thread(workers.shutdown, wait=True, cancel_futures=True)
        await asyncio.to_thread(retriever.close)


def main() -> None:
    """Load the single explicit child config and keep stdout protocol-only."""
    logging.getLogger("mcp").addHandler(logging.NullHandler())
    logging.getLogger("mcp").propagate = False
    try:
        config = RetrievalConfig.model_validate_json(
            os.environ.get("KAOYAN_MCP_RETRIEVAL_CONFIG", "")
        )
        asyncio.run(serve(config))
    except Exception as error:
        logging.getLogger(__name__).error("mcpServerFailure=%s", type(error).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
