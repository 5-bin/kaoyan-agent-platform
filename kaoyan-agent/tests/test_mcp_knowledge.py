"""Real stdio MCP, native HelloAgents, evidence and lifecycle regressions."""

import asyncio
import copy
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from mcp import StdioServerParameters, types
from mcp.client import stdio
from pydantic import ValidationError

from config import ROOT, Settings
from core.framework import Tool
from core.mcp_client import McpKnowledgeClient, McpKnowledgeSearchTool
from core.mcp_contract import KnowledgeResult, RetrievalConfig, output_schema
from core.runtime import CallBudget, retrieval_budget
from main import create_app
from retrieval import Corpus, Retriever, VectorIndex
from schemas import Answer
from tests.test_workflows import FakeModel, HEADERS, KEY, request
from tools.knowledge import KnowledgeSearchTool


def settings(**changes: object) -> Settings:
    """Use frozen fixtures and never load local dotenv configuration."""
    values = dict(_env_file=None, AGENT_INTERNAL_KEY=KEY, LLM_ENABLED=False,
                  RAG_DATA=ROOT / "knowledge/corpus.json")
    values.update(changes)
    return Settings(**values)


def make_client(config: Settings | None = None) -> McpKnowledgeClient:
    """Build a disconnected client using only the declared fixture corpus."""
    config = config or settings()
    return McpKnowledgeClient(config, Corpus(config.RAG_DATA, config.RAG_SOURCE_POLICY_FILE))


def probe_parameters(
    client: McpKnowledgeClient, events: Path, mode: str = "normal"
) -> StdioServerParameters:
    """Replace only the subprocess entrypoint in explicit lifecycle tests."""
    parameters = client.server_parameters()
    return parameters.model_copy(update={
        "args": ["-m", "tests.mcp_probe_server"],
        "env": {**parameters.env, "MCP_TEST_EVENTS": str(events), "MCP_TEST_MODE": mode},
    })


async def wait_event(path: Path, value: str) -> None:
    """Bound polling to a synthetic subprocess event, not a guessed startup delay."""
    async with asyncio.timeout(3):
        while not path.exists() or value not in path.read_text().splitlines():
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["lexical", "bm25", "hybrid"])
async def test_real_stdio_native_tool_matches_local_without_model(
    backend: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Compare complete documents and ordering through a real child process."""
    config = settings(RAG_BACKEND=backend, RAG_INDEX=tmp_path / "missing-index")
    client = make_client(config)
    processes = []
    create = stdio._create_platform_compatible_process

    async def capture(*args, **kwargs):
        process = await create(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(stdio, "_create_platform_compatible_process", capture)
    local = Retriever(config, client.corpus, local_files_only=True)
    adapter = McpKnowledgeSearchTool(client)
    assert isinstance(adapter, Tool)
    assert not processes and client.session is None
    try:
        async with client.connect():
            assert len(processes) == 1
            for query, subject in [
                ("进程与线程", None), ("TCP可靠传输", "计算机网络"),
                ("进程", "计算机网络"), ("海水观赏鱼繁育", None),
            ]:
                expected = local.search(query, "knowledge", 5, subject)
                hits = await adapter.ainvoke({"query": query, "subject": subject})
                assert [hit.metadata["chunk"] for hit in hits] == expected
                assert [hit.page_content for hit in hits] == [doc.content for doc in expected]
    finally:
        local.close()
    assert client.session is None
    assert all(process.returncode is not None for process in processes)
    assert not config.RAG_INDEX.exists()


@pytest.mark.asyncio
async def test_server_rejects_unknown_tools_extra_fields_and_invalid_queries() -> None:
    """Reject direct protocol calls even when bypassing the application adapter."""
    client = make_client()
    async with client.connect():
        for name, arguments in [
            ("execute_sql", {"query": "进程"}),
            ("retrieve_knowledge", {"query": "进程", "userId": 7}),
            ("retrieve_knowledge", {"query": "进程", "path": "/tmp/private"}),
            ("retrieve_knowledge", {"query": ""}),
            ("retrieve_knowledge", {"query": "x" * 8001}),
        ]:
            result = await client.session.call_tool(name, arguments)
            assert result.isError
        assert await client.search("进程与线程")


def valid_result(client: McpKnowledgeClient) -> dict:
    """Return legitimate frozen evidence for adversarial response checks."""
    return KnowledgeResult(
        releaseId=client.corpus.release_id, retrievalBackend=client.config.RAG_BACKEND,
        documents=client.corpus.lexical("进程与线程", "knowledge"),
    ).model_dump(mode="json")


@pytest.mark.parametrize("change", [
    "version", "backend", "extra", "unknown", "duplicate", "too_many",
    "content", "source", "title", "oversize", "unverified", "missing",
])
def test_client_rejects_forged_or_oversized_evidence(change: str) -> None:
    """Do not trust successful protocol status or server-side schema validation."""
    client = make_client()
    value = valid_result(client)
    row = value["documents"][0]
    if change == "version":
        value["releaseId"] = "rag-v1-" + "0" * 16
    elif change == "backend":
        value["retrievalBackend"] = "bm25"
    elif change == "extra":
        value["ownerId"] = 99
    elif change == "unknown":
        row["id"] = "unauthorized#0"
    elif change == "duplicate":
        value["documents"].append(copy.deepcopy(row))
    elif change == "too_many":
        value["documents"] = [row] * 6
    elif change == "content":
        row["content"] = "伪造资料"
    elif change == "source":
        row["url"] = "https://attacker.invalid/private"
    elif change == "title":
        row["title"] = "被篡改的标题"
    elif change == "oversize":
        row["metadata"]["extra"] = "隐私" * 20000
    elif change == "unverified":
        row["reviewStatus"] = "draft"
    else:
        del row["locator"]
    with pytest.raises(ValueError):
        client.validate_result(value)


def test_child_environment_excludes_parent_secrets_and_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parent business/model credentials never enter the spawned child env."""
    for name in ["LLM_API_KEY", "DB_PASSWORD", "AGENT_INTERNAL_KEY", "JWT_SECRET"]:
        monkeypatch.setenv(name, "must-not-be-inherited")
    client = make_client()
    parameters = client.server_parameters()
    inherited = {**stdio.get_default_environment(), **parameters.env}
    assert "must-not-be-inherited" not in json.dumps(inherited)
    config = RetrievalConfig.model_validate_json(inherited["KAOYAN_MCP_RETRIEVAL_CONFIG"])
    assert config.RAG_DATA.is_absolute()
    assert inherited["PYTHON_DOTENV_DISABLED"] == "1"
    assert inherited["HF_HUB_OFFLINE"] == "1"


def test_tool_catalog_and_schema_drift_are_rejected() -> None:
    """Additional tools and changed schemas cannot widen the local whitelist."""
    tool = types.Tool(name="retrieve_knowledge", inputSchema={}, outputSchema=output_schema())
    for tools in [[], [tool], [tool, tool]]:
        with pytest.raises(ValueError):
            McpKnowledgeClient.validate_tools(types.ListToolsResult(tools=tools))


@pytest.mark.asyncio
async def test_three_attempt_budget_is_shared_across_parallel_tool_calls() -> None:
    """Rejected attempts do not open an MCP request or trigger a local retry."""
    client = make_client()
    async with client.connect():
        budget = CallBudget(3)
        token = retrieval_budget.set(budget)
        try:
            results = await asyncio.gather(
                *(client.search("进程与线程") for _ in range(6)), return_exceptions=True
            )
            assert budget.used == 3
            assert sum(isinstance(value, RuntimeError) for value in results) == 3
            assert sum(isinstance(value, list) for value in results) == 3
        finally:
            retrieval_budget.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout", [False, True])
async def test_cancellation_reaches_peer_without_breaking_other_requests(
    timeout: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Observe the real server's cancelled handler and reuse the shared session."""
    client = make_client()
    events = tmp_path / "events.txt"
    parameters = probe_parameters(client, events)
    monkeypatch.setattr(client, "server_parameters", lambda: parameters)
    async with client.connect():
        client.call_timeout = 0.3 if timeout else 5
        slow = asyncio.create_task(client.search("delay"))
        await wait_event(events, "started")
        assert await client.search("进程与线程")
        if not timeout:
            slow.cancel()
        with pytest.raises(RuntimeError if timeout else asyncio.CancelledError):
            await slow
        await wait_event(events, "cancelled")
        assert await client.search("进程与线程")


@pytest.mark.asyncio
async def test_real_child_death_fails_without_local_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abrupt EOF is a bounded failure and cannot turn into a local success."""
    client = make_client()
    parameters = probe_parameters(client, tmp_path / "events")
    monkeypatch.setattr(client, "server_parameters", lambda: parameters)
    async with client.connect():
        with pytest.raises(RuntimeError, match="CONNECTION_CLOSED"):
            await asyncio.wait_for(client.search("exit"), timeout=2)


@pytest.mark.asyncio
async def test_startup_rejects_wrong_catalog_and_cleans_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Startup validation failures leave no active session or child process."""
    client = make_client()
    parameters = probe_parameters(client, tmp_path / "events", "catalog")
    monkeypatch.setattr(client, "server_parameters", lambda: parameters)
    processes = []
    create = stdio._create_platform_compatible_process

    async def capture(*args, **kwargs):
        process = await create(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(stdio, "_create_platform_compatible_process", capture)
    with pytest.raises(Exception):
        async with client.connect():
            pytest.fail("unexpected startup success")
    assert client.session is None and processes
    assert all(process.returncode is not None for process in processes)


@pytest.mark.asyncio
async def test_production_workers_stay_bounded_after_cancelling_running_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancellation does not create unlimited replacement synchronous threads."""
    client = make_client()
    events = tmp_path / "workers.txt"
    parameters = probe_parameters(client, events, "workers")
    monkeypatch.setattr(client, "server_parameters", lambda: parameters)
    async with client.connect():
        pending = [asyncio.create_task(client.search("进程与线程")) for _ in range(6)]
        await wait_event(events, "active=2")
        for task in pending[:2]:
            task.cancel()
        results = await asyncio.gather(*pending, return_exceptions=True)
        assert sum(isinstance(value, asyncio.CancelledError) for value in results) == 2
        assert await client.search("进程与线程")
    counts = [int(line.split("=")[1]) for line in events.read_text().splitlines()]
    assert max(counts) == 2 and counts[-1] == 0


def test_local_mode_never_connects_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default behavior remains the existing native local tool without a child."""
    def forbidden(*args, **kwargs):
        pytest.fail("local mode attempted MCP startup")

    monkeypatch.setattr(McpKnowledgeClient, "connect", forbidden)
    model = FakeModel(error=True)
    with TestClient(create_app(settings(), model=model)) as client:
        response = client.post("/internal/rag/chat", headers=HEADERS,
                               json=request("KNOWLEDGE_QA", userInput="进程与线程"))
        assert response.json()["status"] == "SUCCESS"
        assert isinstance(client.app.state.engine.knowledge_search, KnowledgeSearchTool)
    assert model.calls == 0


def test_mcp_sync_chat_sse_and_learning_are_compatible() -> None:
    """Real FastAPI + HelloAgents + stdio, without external model requests."""
    config = settings(KNOWLEDGE_TOOL_TRANSPORT="mcp_stdio")
    model = FakeModel(error=True)
    app = create_app(config, model=model)
    with TestClient(app) as client:
        assert isinstance(app.state.engine.knowledge_search, Tool)
        for query in ["进程与线程", "TCP可靠传输"]:
            result = client.post("/internal/rag/chat", headers=HEADERS,
                                 json=request("KNOWLEDGE_QA", userInput=query)).json()
            assert result["status"] == "SUCCESS" and result["references"]
        body = request("CHAT", userInput="进程与线程")
        planned = client.post("/internal/rag/conversation/plan", headers=HEADERS, json=body)
        assert planned.status_code == 200
        body["preparedPlan"] = planned.json()
        stream = client.post("/internal/rag/conversation/stream", headers=HEADERS, json=body)
        rows = [json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith("data: ")]
        assert any(row["type"] == "result" and row["response"]["references"] for row in rows)
        body = request("CHAT", userInput="分析我的薄弱点，安排3天复习计划")
        plan = client.post("/internal/rag/conversation/plan", headers=HEADERS, json=body).json()
        body.update(preparedPlan=plan, learningContext={"statistics":{
            "questionCount":3,"correctCount":1,
            "knowledgePoints":[{"knowledgePoint":"线程","questionCount":3}],
        }})
        stream = client.post("/internal/rag/conversation/stream", headers=HEADERS, json=body)
        rows = [json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith("data: ")]
        result = next(row["response"]["result"] for row in rows if row["type"] == "result")
        assert len(result["studyPlan"]["days"]) == 3
        assert result["references"]
        assert app.state.engine.retriever.vector is None
    assert app.state.mcp_client.session is None
    assert model.calls == 0


def test_missing_vector_index_fails_before_open_or_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP read-only mode never creates or populates a missing vector index."""
    from qdrant_client import QdrantClient

    def forbidden(*args, **kwargs):
        pytest.fail("missing read-only index opened Qdrant")

    monkeypatch.setattr(QdrantClient, "__init__", forbidden)
    config = settings(RAG_BACKEND="qdrant", RAG_INDEX=tmp_path / "absent")
    with pytest.raises(RuntimeError, match="向量索引尚未构建"):
        VectorIndex(config, make_client(config).corpus, local_files_only=True)
    assert not config.RAG_INDEX.exists()


def test_transport_configuration_rejects_unknown_values() -> None:
    """The transport switch never accepts an arbitrary remote endpoint."""
    with pytest.raises(ValidationError):
        settings(KNOWLEDGE_TOOL_TRANSPORT="https://attacker.invalid/mcp")


@pytest.mark.asyncio
async def test_startup_timeout_reaps_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A hung initializer cannot outlive the configured startup deadline."""
    client = make_client()
    parameters = probe_parameters(client, tmp_path / "events", "startup_delay")
    monkeypatch.setattr(client, "server_parameters", lambda: parameters)
    client.startup_timeout = 0.5
    processes = []
    create = stdio._create_platform_compatible_process

    async def capture(*args, **kwargs):
        process = await create(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(stdio, "_create_platform_compatible_process", capture)
    with pytest.raises(Exception):
        async with client.connect():
            pytest.fail("startup timeout did not fire")
    assert client.session is None and processes
    assert all(process.returncode is not None for process in processes)


@pytest.mark.asyncio
async def test_health_stays_responsive_during_real_synchronous_mcp_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The old synchronous HTTP endpoint does not block the event loop."""
    app = create_app(settings(KNOWLEDGE_TOOL_TRANSPORT="mcp_stdio"), model=FakeModel(error=True))
    events = tmp_path / "workers"
    parameters = probe_parameters(app.state.mcp_client, events, "workers")
    monkeypatch.setattr(app.state.mcp_client, "server_parameters", lambda: parameters)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            pending = asyncio.create_task(client.post(
                "/internal/rag/chat", headers=HEADERS,
                json=request("KNOWLEDGE_QA", userInput="进程与线程"),
            ))
            await wait_event(events, "active=1")
            health = await asyncio.wait_for(client.get("/health"), timeout=0.15)
            assert health.status_code == 200
            assert not pending.done()
            assert (await pending).json()["status"] == "SUCCESS"


def test_invalid_ai_citation_preserves_mcp_evidence() -> None:
    """A model cannot manufacture sources merely because retrieval uses MCP."""
    model = FakeModel(Answer(answer="伪造解释不得显示", sourceIds=["not-authorized"]))
    config = settings(KNOWLEDGE_TOOL_TRANSPORT="mcp_stdio", LLM_ENABLED=True,
                      LLM_API_KEY="synthetic-test-only")
    with TestClient(create_app(config, model=model)) as client:
        result = client.post("/internal/rag/chat", headers=HEADERS,
                             json=request("KNOWLEDGE_QA", userInput="进程与线程")).json()
    assert result["status"] == "SUCCESS" and model.calls == 1
    assert result["result"]["explanationMode"] == "fallback"
    assert "伪造解释" not in result["result"]["answer"]
    assert result["references"] and all(ref["id"] != "not-authorized" for ref in result["references"])


def test_wrong_subject_hint_falls_back_within_same_request_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """The knowledge expert retains its filtered-then-unfiltered search behavior."""
    import agents.knowledge as module

    monkeypatch.setattr(module, "subject_terms", lambda query: ("计算机网络", ()))
    model = FakeModel(error=True)
    with TestClient(create_app(settings(KNOWLEDGE_TOOL_TRANSPORT="mcp_stdio"), model=model)) as client:
        result = client.post("/internal/rag/chat", headers=HEADERS,
                             json=request("KNOWLEDGE_QA", userInput="进程与线程")).json()
    assert result["status"] == "SUCCESS" and result["references"]
    assert model.calls == 0


@pytest.mark.asyncio
async def test_server_rejects_oversized_structured_result(tmp_path: Path) -> None:
    """The real server rejects excessive metadata without truncating evidence."""
    records = json.loads((ROOT / "knowledge/corpus.json").read_text())
    for row in records:
        if row["domain"] == "knowledge":
            row.setdefault("metadata", {})["large_test_field"] = "大" * 23000
    data = tmp_path / "oversized.json"
    data.write_text(json.dumps(records, ensure_ascii=False))
    client = make_client(settings(RAG_DATA=data))
    async with client.connect():
        result = await client.session.call_tool("retrieve_knowledge", {"query": "进程与线程"})
        assert result.isError and result.structuredContent is None
        assert "large_test_field" not in str(result)


@pytest.mark.asyncio
async def test_accounts_share_connection_but_not_results_or_request_budgets() -> None:
    """Concurrent requests retain their own task identity, query and allowances."""
    app = create_app(settings(KNOWLEDGE_TOOL_TRANSPORT="mcp_stdio"), model=FakeModel(error=True))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            bodies = [request("KNOWLEDGE_QA", taskId=f"isolated-{index}", userId=1 + index % 2,
                              userInput="进程与线程" if index % 2 else "TCP可靠传输")
                      for index in range(6)]
            responses = await asyncio.gather(*(
                client.post("/internal/rag/chat", headers=HEADERS, json=body)
                for body in bodies
            ))
            for body, response in zip(bodies, responses):
                result = response.json()
                assert result["status"] == "SUCCESS" and result["taskId"] == body["taskId"]
                prefix = "os-" if body["userId"] == 2 else "cn-"
                assert all(ref["id"].startswith(prefix) for ref in result["references"])


@pytest.mark.asyncio
async def test_qdrant_is_owned_only_by_child_and_released_on_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real temporary Qdrant reopens after the MCP owner exits; vectors are fake."""
    from qdrant_client import QdrantClient
    from tests.mcp_probe_server import FixtureEncoder

    config = settings(RAG_BACKEND="qdrant", RAG_INDEX=tmp_path / "rag", RAG_MIN_SCORE=0)
    client = make_client(config)
    index = VectorIndex(config, client.corpus, FixtureEncoder())
    try:
        index.build()
        expected = index.search("进程与线程", "knowledge")
    finally:
        index.close()
    parameters = probe_parameters(client, tmp_path / "events", "qdrant")
    monkeypatch.setattr(client, "server_parameters", lambda: parameters)
    async with client.connect():
        assert await client.search("进程与线程") == expected
        with pytest.raises(RuntimeError, match="already accessed"):
            QdrantClient(path=str(config.RAG_INDEX / "qdrant"))
    reopened = QdrantClient(path=str(config.RAG_INDEX / "qdrant"))
    reopened.close()
