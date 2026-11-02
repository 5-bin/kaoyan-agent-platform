"""Controlled subprocess peers for lifecycle tests; never used by production."""

import asyncio
import os
import threading
import time
from pathlib import Path

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from core.mcp_contract import (
    TOOL_NAME,
    KnowledgeResult,
    RetrievalConfig,
    input_schema,
    output_schema,
)
from retrieval import Corpus


class FixtureEncoder:
    """Small deterministic vectors for temporary Qdrant ownership checks."""

    def __init__(self, model: str = "fixture", *, cache_dir: str | None = None, local_files_only: bool = True) -> None:
        """Forbid a child encoder that could attempt network model downloads."""
        assert local_files_only

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Return reproducible nonzero vectors without loading model weights."""
        return [[1.0 + text.count("进程"), 1.0 + text.lower().count("tcp"), 1.0]
                for text in texts]


def event(value: str) -> None:
    """Write synthetic lifecycle evidence only to the test-owned temporary file."""
    with Path(os.environ["MCP_TEST_EVENTS"]).open("a") as output:
        output.write(value + "\n")


async def probe() -> None:
    """Exercise SDK cancellation and abrupt process death over real stdio."""
    config = RetrievalConfig.model_validate_json(os.environ["KAOYAN_MCP_RETRIEVAL_CONFIG"])
    corpus = Corpus(config.RAG_DATA, config.RAG_SOURCE_POLICY_FILE)
    if os.environ.get("MCP_TEST_MODE") == "startup_delay":
        event("starting")
        await asyncio.sleep(30)
    server = Server("mcp-lifecycle-probe")

    @server.list_tools()
    async def catalog() -> list[types.Tool]:
        """Match production schemas unless testing startup rejection."""
        return [types.Tool(
            name="unexpected" if os.environ.get("MCP_TEST_MODE") == "catalog" else TOOL_NAME,
            inputSchema=input_schema(), outputSchema=output_schema(),
        )]

    @server.call_tool()
    async def call(name: str, arguments: dict) -> dict:
        """Return frozen evidence, or expose a test-only cancellable delay."""
        query = arguments["query"]
        if query == "exit":
            os._exit(23)
        if query == "delay":
            event("started")
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                event("cancelled")
                raise
        documents = corpus.lexical("进程与线程", "knowledge")
        return KnowledgeResult(
            releaseId=corpus.release_id, retrievalBackend=config.RAG_BACKEND,
            documents=documents,
        ).model_dump(mode="json")

    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


async def workers() -> None:
    """Exercise the production server's real synchronous worker pool."""
    from mcp_server import serve
    from tools.knowledge import KnowledgeSearchTool

    original = KnowledgeSearchTool.run
    lock = threading.Lock()
    active = 0

    def delayed(self: KnowledgeSearchTool, parameters: dict) -> str:
        """Track live reads while allowing cancellation of their awaiting tasks."""
        nonlocal active
        with lock:
            active += 1
            event("active=" + str(active))
        try:
            time.sleep(0.3)
            return original(self, parameters)
        finally:
            with lock:
                active -= 1
                event("active=" + str(active))

    KnowledgeSearchTool.run = delayed
    config = RetrievalConfig.model_validate_json(os.environ["KAOYAN_MCP_RETRIEVAL_CONFIG"])
    await serve(config)


async def vector() -> None:
    """Use production serving and Qdrant with an explicitly synthetic encoder."""
    import retrieval
    from mcp_server import serve

    retrieval.FastEmbedEncoder = FixtureEncoder
    config = RetrievalConfig.model_validate_json(os.environ["KAOYAN_MCP_RETRIEVAL_CONFIG"])
    await serve(config)


if __name__ == "__main__":
    mode = os.environ.get("MCP_TEST_MODE")
    if mode == "workers":
        asyncio.run(workers())
    elif mode == "qdrant":
        asyncio.run(vector())
    else:
        asyncio.run(probe())
