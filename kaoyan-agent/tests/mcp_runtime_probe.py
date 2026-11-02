"""Fault-injecting real stdio peer; never imported by a production entrypoint."""

import asyncio
import os
from pathlib import Path

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.shared.message import SessionMessage

from admission_mcp_server import AdmissionConfig
from core.admission_contract import AdmissionLinksRegistry, AdmissionLinksResult
from core.mcp_contract import KnowledgeResult, RetrievalConfig
from retrieval import Corpus
from schemas import AdmissionLinksQuery
from tools.knowledge import SearchParameters


def event(value: str) -> None:
    """Write only synthetic lifecycle markers into a test-owned file."""
    with Path(os.environ["RUNTIME_PROBE_EVENTS"]).open("a") as target:
        target.write(value + "\n")


async def main() -> None:
    """Advertise production schemas and simulate connection and result failures."""
    knowledge = "KAOYAN_MCP_RETRIEVAL_CONFIG" in os.environ
    mode = os.environ.get("RUNTIME_PROBE_MODE", "normal")
    registry = None
    if knowledge:
        config = RetrievalConfig.model_validate_json(
            os.environ["KAOYAN_MCP_RETRIEVAL_CONFIG"]
        )
        corpus = Corpus(config.RAG_DATA, config.RAG_SOURCE_POLICY_FILE)
        tool_name = "retrieve_knowledge"
        parameters = SearchParameters
        result_model = KnowledgeResult
    else:
        config = AdmissionConfig.model_validate_json(
            os.environ["KAOYAN_ADMISSION_CONFIG"]
        )
        registry = AdmissionLinksRegistry(config.sourcePath)
        tool_name = "get_admission_links"
        parameters = AdmissionLinksQuery
        result_model = AdmissionLinksResult
    event("pid=" + str(os.getpid()))
    if mode == "startup-timeout":
        await asyncio.sleep(30)
    server = Server("reliability-test-peer")

    async def exit_idle() -> None:
        await asyncio.sleep(0.2)
        os._exit(21)

    @server.list_tools()
    async def catalog() -> list[types.Tool]:
        """Schedule an idle EOF or return a deliberately incorrect catalog."""
        if mode == "idle-exit":
            asyncio.create_task(exit_idle())
        return [types.Tool(
            name="unexpected" if mode == "catalog" else tool_name,
            inputSchema={} if mode == "schema" else parameters.model_json_schema(),
            outputSchema=result_model.model_json_schema(),
            annotations=types.ToolAnnotations(
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )]

    @server.call_tool()
    async def call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        """Return a forged link result, an error, a cancellable wait or EOF."""
        event("call")
        if mode == "exit":
            os._exit(22)
        if mode == "tool-error":
            raise ValueError("secret-untrusted-query-and-token")
        if mode == "malformed-notification":
            await server.request_context.session._write_stream.send(SessionMessage(
                message=types.JSONRPCMessage(types.JSONRPCNotification(
                    jsonrpc="2.0", method="notifications/progress",
                    params={"progressToken": 1, "progress": "secret-untrusted-query-and-token"},
                )),
            ))
        if mode == "slow":
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                event("cancelled")
                raise
        if knowledge:
            release_id = "rag-v1-0000000000000000" if mode == "forged" else corpus.release_id
            return KnowledgeResult(
                releaseId=release_id,
                retrievalBackend=config.RAG_BACKEND,
                documents=[],
            ).model_dump(mode="json")
        assert registry is not None
        result = registry.get(AdmissionLinksQuery.model_validate(arguments))
        if mode == "forged":
            result = result.model_copy(update={"registeredYear": 2000})
        return result.model_dump(mode="json")

    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
