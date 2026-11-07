"""Real stdio availability, request budgets, diagnostic privacy and API isolation."""

import asyncio
import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Literal

import psutil
import pytest
from fastapi.testclient import TestClient
from mcp import ClientSession, types
from pydantic import ValidationError

from conversation import ConversationWorkflow
from core.admission_client import McpAdmissionClient
from core.mcp_client import McpKnowledgeClient
from core.mcp_runtime import CancellingClientSession, McpCallError, McpErrorCode, McpState, OwnedMcpClient
from core.runtime import CallBudget, admission_budget, retrieval_budget
from main import create_app
from schemas import ConversationResolution
from tests.test_admission import corpus, query, settings
from tests.test_workflows import FakeModel, HEADERS, request

Kind = Literal["knowledge", "admission"]


def configure(client: OwnedMcpClient, events: Path, mode: str) -> None:
    """Inject a fixed test peer without exposing arbitrary commands in production."""
    original = client.server_parameters()
    parameters = original.model_copy(update={
        "args": ["-m", "tests.mcp_runtime_probe"],
        "env": {**original.env, "RUNTIME_PROBE_EVENTS": str(events), "RUNTIME_PROBE_MODE": mode},
    })
    client.server_parameters = lambda: parameters


def make_client(kind: Kind, events: Path, mode: str = "normal") -> OwnedMcpClient:
    """Create an isolated client with the frozen test corpus."""
    client = McpKnowledgeClient(settings(), corpus()) if kind == "knowledge" else McpAdmissionClient()
    configure(client, events, mode)
    return client


async def invoke(client: OwnedMcpClient) -> object:
    """Use the real domain adapter, not the raw session, in every call test."""
    if isinstance(client, McpAdmissionClient):
        return await client.check(**query().model_dump())
    assert isinstance(client, McpKnowledgeClient)
    return await client.search("secret-untrusted-query-and-token")


async def wait_for_event(events: Path, marker: str) -> None:
    """Wait a bounded time for the real child lifecycle marker."""
    async with asyncio.timeout(4):
        while not events.exists() or marker not in events.read_text().splitlines():
            await asyncio.sleep(.01)


def assert_reaped(events: Path) -> None:
    """Check that all captured test peer PIDs have exited."""
    pids = [int(line[4:]) for line in events.read_text().splitlines() if line.startswith("pid=")]
    assert pids and all(not psutil.pid_exists(pid) for pid in pids)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["knowledge", "admission"])
@pytest.mark.parametrize("mode,code", [
    ("catalog", McpErrorCode.CATALOG_CHANGED),
    ("schema", McpErrorCode.SCHEMA_CHANGED),
    ("startup-timeout", McpErrorCode.TIMEOUT),
])
async def test_startup_failure_is_isolated_and_reaps_child(kind: Kind, mode: str, code: McpErrorCode, tmp_path: Path) -> None:
    """A failed enabled tool remains unavailable without leaking its process."""
    events = tmp_path / "events"
    client = make_client(kind, events, mode)
    if mode == "startup-timeout":
        # Give the real child time to import and write its pid before the deadline;
        # 0.7s is too tight on CI and made assert_reaped race the child.
        client.startup_timeout = 5
    async with client.connect(isolate_failure=True):
        assert client.status.snapshot() == {"enabled": True, "state": "UNAVAILABLE", "errorCode": code.value}
        with pytest.raises(McpCallError) as caught:
            await invoke(client)
        assert caught.value.code == code
        assert client.session is None
        assert_reaped(events)
    assert client.status.state == McpState.CLOSED


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["knowledge", "admission"])
async def test_missing_executable_is_safe_start_failure(kind: Kind, tmp_path: Path) -> None:
    """An OS startup exception is classified without returning its raw details."""
    client = make_client(kind, tmp_path / "events")
    params = client.server_parameters().model_copy(update={"command": "/no-such-mcp-command"})
    client.server_parameters = lambda: params
    async with client.connect(isolate_failure=True):
        assert client.status.error_code == McpErrorCode.START_FAILED
        with pytest.raises(McpCallError, match="START_FAILED"):
            await invoke(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["knowledge", "admission"])
async def test_cancel_during_startup_reaps_child(kind: Kind, tmp_path: Path) -> None:
    """Cancellation before initialization cannot leave an owner or peer alive."""
    events = tmp_path / "events"
    client = make_client(kind, events, "startup-timeout")

    async def start() -> None:
        async with client.connect():
            pytest.fail("hung initializer became ready")

    starting = asyncio.create_task(start())
    async with asyncio.timeout(4):
        while not events.exists():
            await asyncio.sleep(.01)
    starting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(starting, 4)
    assert client._owner.done() and client.session is None
    assert client.status.state == McpState.CLOSED
    assert_reaped(events)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["knowledge", "admission"])
@pytest.mark.parametrize("mode", ["idle-exit", "exit"])
async def test_connection_exit_fails_fast_without_recovery(kind: Kind, mode: str, tmp_path: Path) -> None:
    """Detect idle EOF as well as a child dying while its call is pending."""
    events = tmp_path / "events"
    client = make_client(kind, events, mode)
    budget = CallBudget(3)
    token = (admission_budget if kind == "admission" else retrieval_budget).set(budget)
    try:
        async with client.connect():
            if mode == "exit":
                with pytest.raises(McpCallError, match="CONNECTION_CLOSED"):
                    await asyncio.wait_for(invoke(client), 2)
            async with asyncio.timeout(3):
                while client.status.state != McpState.UNAVAILABLE:
                    await asyncio.sleep(.01)
            used = budget.used
            with pytest.raises(McpCallError, match="CONNECTION_CLOSED"):
                await asyncio.wait_for(invoke(client), .1)
            assert budget.used == used
            assert len([line for line in events.read_text().splitlines() if line.startswith("pid=")]) == 1
        assert_reaped(events)
    finally:
        (admission_budget if kind == "admission" else retrieval_budget).reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["knowledge", "admission"])
@pytest.mark.parametrize("mode,code", [("forged", McpErrorCode.RESULT_INVALID), ("tool-error", McpErrorCode.TOOL_FAILED)])
async def test_rejected_result_keeps_connection_and_sanitizes_logs(kind: Kind, mode: str, code: McpErrorCode, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Business/tool failure is not misreported as a dead transport."""
    caplog.set_level(logging.INFO)
    events = tmp_path / "events"
    client = make_client(kind, events, mode)
    token = (admission_budget if kind == "admission" else retrieval_budget).set(CallBudget(3))
    try:
        async with client.connect():
            for _ in range(2):
                with pytest.raises(McpCallError) as caught:
                    await invoke(client)
                assert caught.value.code == code
                assert str(caught.value) == code.value
                assert client.status.state == McpState.READY
            assert events.read_text().splitlines().count("call") == 2
    finally:
        (admission_budget if kind == "admission" else retrieval_budget).reset(token)
    assert "secret-untrusted-query-and-token" not in caplog.text
    assert "outcome=" + code.value in caplog.text
    assert "budgetUsed=2" in caplog.text and "id=" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["knowledge", "admission"])
async def test_shutdown_cancels_only_owned_calls_and_reaps_peer(kind: Kind, tmp_path: Path) -> None:
    """Exiting the owner context cancels pending RPCs and blocks further calls."""
    events = tmp_path / "events"
    client = make_client(kind, events, "slow")
    async with client.connect():
        caller = asyncio.create_task(invoke(client))
        await wait_for_event(events, "call")
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert not client._active and client.session is None
    assert client.status.state == McpState.CLOSED
    assert_reaped(events)
    with pytest.raises(McpCallError, match="CONNECTION_CLOSED"):
        await asyncio.wait_for(invoke(client), .1)


@pytest.mark.asyncio
async def test_shared_admission_budget_parallel_requests_and_preflight(tmp_path: Path) -> None:
    """Three sibling tasks reserve one attempt; invalid/unavailable calls reserve none."""
    events = tmp_path / "events"
    client = make_client("admission", events)
    budget = CallBudget(1)
    token = admission_budget.set(budget)
    try:
        with pytest.raises(McpCallError):
            await invoke(client)
        assert budget.used == 0
        async with client.connect():
            with pytest.raises(ValidationError):
                await client.check(**query().model_dump(), url="https://invalid.example")
            assert budget.used == 0
            responses = await asyncio.gather(*(invoke(client) for _ in range(3)), return_exceptions=True)
            assert sum(isinstance(row, dict) for row in responses) == 1
            assert sum(isinstance(row, McpCallError) and row.code == McpErrorCode.CALL_LIMIT for row in responses) == 2
            assert budget.used == 1
            admission_budget.set(CallBudget(1))
            assert isinstance(await invoke(client), dict)
        assert events.read_text().splitlines().count("call") == 2
    finally:
        admission_budget.reset(token)


@pytest.mark.parametrize("failed", ["knowledge", "admission"])
def test_app_isolates_one_tool_and_health_never_calls_tools(failed: Kind, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both are enabled; only one fails, and HTTP handlers stay available."""
    app = create_app(settings(KNOWLEDGE_TOOL_TRANSPORT="mcp_stdio", ADMISSION_MCP_ENABLED=True), model=FakeModel(error=True))
    for kind, client in [("knowledge", app.state.mcp_client), ("admission", app.state.admission_client)]:
        configure(client, tmp_path / kind, "catalog" if kind == failed else "normal")
    with TestClient(app) as http:
        for _ in range(2):
            health = http.get("/health").json()
            assert health["status"] == "ok"
            assert health["mcpTools"][failed]["state"] == "UNAVAILABLE"
            assert health["mcpTools"][failed]["enabled"] is True
            other = "admission" if failed == "knowledge" else "knowledge"
            assert health["mcpTools"][other]["state"] == "READY"
        assert all("call" not in (tmp_path / kind).read_text().splitlines() for kind in ("knowledge", "admission"))
        response = http.post("/internal/rag/chat", headers=HEADERS, json=request("KNOWLEDGE_QA", userInput="解释进程"))
        assert response.json()["status"] == ("FAILED" if failed == "knowledge" else "SUCCESS")
        body = request("CHAT", userInput="查官网南京审计大学")
        plan = http.post("/internal/rag/conversation/plan", headers=HEADERS, json=body).json()
        response = http.post("/internal/rag/conversation/stream", headers=HEADERS, json={**body, "preparedPlan": plan})
        assert '"type": "result"' in response.text
        if failed == "admission":
            assert "工具清单不符合约定" in response.text
    for kind in ("knowledge", "admission"):
        assert_reaped(tmp_path / kind)


def test_app_disabled_health_and_request_scopes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sync, planning and SSE each share one budget and reset it for new requests."""
    app = create_app(settings(ADMISSION_MCP_ENABLED=True), model=FakeModel(error=True))
    events = tmp_path / "events"
    configure(app.state.admission_client, events, "normal")
    budgets: list[CallBudget] = []

    async def calls() -> None:
        budgets.append(admission_budget.get())
        responses = await asyncio.gather(*(invoke(app.state.admission_client) for _ in range(3)), return_exceptions=True)
        assert sum(isinstance(row, dict) for row in responses) == 1
        assert sum(isinstance(row, McpCallError) and row.code == McpErrorCode.CALL_LIMIT for row in responses) == 2

    async def run(req: object) -> dict[str, object]:
        await calls()
        return {"outcome": "COMPLETED", "answer": "fixture", "references": []}

    async def plan(self: ConversationWorkflow, req: object) -> ConversationResolution:
        await calls()
        return ConversationResolution(action="CHAT", standaloneQuery="fixture")

    async def stream(self: ConversationWorkflow, req: object) -> dict[str, object]:
        return await run(req)

    monkeypatch.setattr(app.state.engine, "run", run)
    monkeypatch.setattr(ConversationWorkflow, "plan", plan)
    monkeypatch.setattr(ConversationWorkflow, "run", stream)
    with TestClient(app) as http:
        assert http.get("/health").json()["mcpTools"]["knowledge"] == {"enabled": False, "state": "DISABLED", "errorCode": None}
        for path in ("chat", "conversation/plan", "conversation/stream"):
            for user in (1, 2):
                response = http.post("/internal/rag/" + path, headers=HEADERS, json=request("CHAT", userId=user))
                assert response.status_code == 200
                if path.endswith("stream"):
                    assert '"type": "result"' in response.text
                elif path == "chat":
                    assert response.json()["status"] == "SUCCESS"
    assert len({id(item) for item in budgets}) == 6
    assert all(item.limit == item.used == 1 for item in budgets)
    assert events.read_text().splitlines().count("call") == 6
    assert admission_budget.get() is None


def test_pinned_sdk_extension_signatures_match() -> None:
    """Protect both private hook and public request signature when upgrading MCP."""
    assert list(inspect.signature(CancellingClientSession.send_request).parameters) == list(inspect.signature(ClientSession.send_request).parameters)
    assert inspect.signature(CancellingClientSession._receive_loop) == inspect.signature(ClientSession._receive_loop)
    assert inspect.signature(CancellingClientSession._validate_tool_result) == inspect.signature(ClientSession._validate_tool_result)


@pytest.mark.asyncio
async def test_sdk_output_schema_failure_has_fixed_category() -> None:
    """Schema errors raised inside the SDK must not escape as arbitrary text."""
    # The hook uses only the output schema cache, so no transport is opened.
    session = object.__new__(CancellingClientSession)
    session._tool_output_schemas = {"fixture": {"type": "object", "required": ["expected"]}}
    with pytest.raises(McpCallError, match="RESULT_INVALID") as caught:
        await session._validate_tool_result("fixture", types.CallToolResult(
            content=[], structuredContent={"secret-untrusted-query-and-token": "x"},
        ))
    assert "secret" not in str(caught.value)


@pytest.mark.asyncio
async def test_sdk_root_diagnostics_never_include_invalid_peer_payload(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Malformed unsolicited notifications take the real SDK root logging path."""
    client = make_client("knowledge", tmp_path / "events", "malformed-notification")
    async with client.connect():
        assert await invoke(client) == []
        assert client.status.state == McpState.READY
    assert "mcpProtocolDiagnostic=REJECTED" in caplog.text
    assert "secret-untrusted-query-and-token" not in caplog.text


@pytest.mark.asyncio
async def test_admission_check_script_offline_and_mcp_share_exact_links() -> None:
    """The CLI exposes configuration by default and one real local protocol smoke path."""
    script = Path(__file__).resolve().parents[2] / "scripts/check-admission.py"
    spec = importlib.util.spec_from_file_location("check_admission_test", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    offline = await module.inspect(False)
    assert offline["mode"] == "offline" and offline["schools"] == len(module.load_sources())
    assert set(offline["results"][0]) == {"schoolCode", "schoolName", "registeredYear", "entryUrls"}
    report = await module.inspect(True)
    assert report["mode"] == "mcp"
    assert report["mcpStatus"]["state"] == "READY"
    assert len(report["results"]) == len(module.load_sources())
    assert all(item["status"] == "OK" for item in report["results"])
