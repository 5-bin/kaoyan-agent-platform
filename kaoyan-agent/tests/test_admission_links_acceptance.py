"""Independent protocol acceptance: the real admission child must work without network/parsers."""

import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agents.planning import admission_links_plan, admission_scope_requested
from core.admission_client import McpAdmissionClient
from core.runtime import CallBudget, admission_budget
from schemas import ConversationRequest


@pytest.mark.parametrize("text", [
    "查官网南京审计大学",
    "给我南京审计大学招生网址",
    "核对南京审计大学招生信息",
    "南京审计大学查官网",
    "请你查官网南京审计大学",
    "南京审计大学的招生信息有什么变化",
])
def test_single_registered_school_does_not_require_year_or_major(text: str) -> None:
    """Polite phrasing and a factual question must not become a multi-school/scope query."""
    assert not admission_scope_requested(text)
    request = ConversationRequest(taskId="synthetic", userId=1, taskType="CHAT", userInput=text)
    plan = admission_links_plan(request)
    assert plan is not None
    assert plan.action == "ADMISSION_LINKS"
    assert plan.clarification is None
    assert plan.admissionLinks.model_dump() == {"schoolCode": "nau"}


@pytest.mark.asyncio
async def test_unknown_school_is_rejected_before_connection_or_budget() -> None:
    """Invalid registry codes cannot submit RPCs or reserve an attempt."""
    client = McpAdmissionClient()
    budget = CallBudget(1)
    token = admission_budget.set(budget)
    try:
        with pytest.raises(ValueError, match="ADMISSION_SOURCE_UNKNOWN"):
            await client.check(schoolCode="unknown")
        assert budget.used == 0
        assert client.session is None
    finally:
        admission_budget.reset(token)


@pytest.mark.asyncio
async def test_real_stdio_links_work_with_network_and_removed_parser_imports_forbidden(
    tmp_path: Path,
) -> None:
    """Run the shipped child with an active guard, not a simulated registry/tool response."""
    agent_root = Path(__file__).resolve().parents[1]
    registry = agent_root.parent / "config/admission-sources.json"
    marker = tmp_path / "guard-events"
    guard = tmp_path / "sitecustomize.py"
    guard.write_text(
        """import importlib.abc
import os
from pathlib import Path
import socket
import sys

marker = Path(os.environ['ADMISSION_GUARD_MARKER'])
marker.write_text('guard-active\\n')

def reject(kind):
    with marker.open('a') as output:
        output.write(kind + '\\n')
    raise AssertionError('ADMISSION_NETWORK_OR_PARSER_FORBIDDEN')

def audit(event, arguments):
    if event in {'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr'}:
        reject('dns')
    if event == 'socket.connect' and arguments[0].family in {socket.AF_INET, socket.AF_INET6}:
        reject('network')

sys.addaudithook(audit)

class NoAdmissionParser(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'pdfplumber', 'admission_pdf_worker', 'tools.admission',
                        'tools.admission_html', 'core.admission_pdf', 'core.admission_diagnostics'}:
            reject('parser:' + fullname)
        return None

sys.meta_path.insert(0, NoAdmissionParser())
import httpx

def no_http(*args, **kwargs):
    reject('http')

async def no_async_http(*args, **kwargs):
    reject('http')

httpx.Client.request = no_http
httpx.AsyncClient.request = no_async_http
""",
        encoding="utf-8",
    )
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "admission_mcp_server"],
        cwd=str(agent_root),
        env={
            "PYTHONPATH": str(tmp_path),
            "PYTHON_DOTENV_DISABLED": "1",
            "KAOYAN_ADMISSION_CONFIG": json.dumps({"sourcePath": str(registry)}),
            "ADMISSION_GUARD_MARKER": str(marker),
        },
    )
    sources = json.loads(registry.read_text("utf-8"))
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            catalog = await session.list_tools()
            assert [tool.name for tool in catalog.tools] == ["get_admission_links"]
            assert catalog.tools[0].annotations.openWorldHint is False
            for source in sources:
                result = await session.call_tool("get_admission_links", {"schoolCode": source["code"]})
                assert not result.isError
                assert result.structuredContent == {
                    "schoolCode": source["code"],
                    "schoolName": source["name"],
                    "registeredYear": source["year"],
                    "entryUrls": source["entries"],
                }
            for arguments in [
                {"schoolCode": "unknown"},
                {"schoolCode": "nau", "year": 2027},
                {"schoolCode": "nau", "url": "https://evil.invalid"},
                {"schoolCode": "nau", "ownerId": 2},
            ]:
                rejected = await session.call_tool("get_admission_links", arguments)
                assert rejected.isError
            rejected = await session.call_tool("check_admission_updates", {"schoolCode": "nau"})
            assert rejected.isError
    assert marker.read_text("utf-8").splitlines() == ["guard-active"]
