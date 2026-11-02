"""Local admission-link registry, real stdio MCP, planning and isolation tests."""

import importlib.util
import json
import socket
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agents.planning import (
    ModelConversationResolution,
    admission_links_plan,
    admission_requested,
    admission_scope_requested,
    admission_source_answer,
    explicit_schools,
)
from config import ROOT, Settings
from core.admission_client import AdmissionLinksTool, McpAdmissionClient
from core.admission_contract import (
    AdmissionLinksRegistry, AdmissionLinksResult, AdmissionSource, TOOL_NAME, load_sources,
)
from core.framework import Tool
from core.mcp_contract import checked_size
from core.mcp_runtime import McpCallError, McpErrorCode
from main import create_app
from retrieval import Corpus
from schemas import AdmissionLinksQuery, ConversationRequest, ConversationResolution
from tests.test_workflows import FakeModel, HEADERS, KEY, request

REAL_CORPUS = ROOT / "knowledge/real-corpus-20261024-a476bf509577d904.json"
NO_NETWORK = Path(__file__).parent / "no_network"


def settings(**values: object) -> Settings:
    """Explicit frozen inputs, never daily dotenv/services or business records."""
    return Settings(_env_file=None, AGENT_INTERNAL_KEY=KEY, RAG_DATA=REAL_CORPUS, **values)


def corpus() -> Corpus:
    """Load the checked-in snapshot for unchanged knowledge lifecycle tests."""
    config = settings()
    return Corpus(config.RAG_DATA, config.RAG_SOURCE_POLICY_FILE)


def query(code: str = "nau", **changes: object) -> AdmissionLinksQuery:
    """Build one exact local link query."""
    return AdmissionLinksQuery.model_validate({"schoolCode": code, **changes})


def conversation(text: str, **changes: object) -> ConversationRequest:
    """Build a minimal valid conversation request without business persistence."""
    body = {
        "taskId": "test-admission-links",
        "userId": 1,
        "taskType": "CHAT",
        "userInput": text,
        "privacy": {"modelAllowed": False, "scopes": [], "provider": None},
    }
    body.update(changes)
    return ConversationRequest.model_validate(body)


def test_config_has_only_simplified_trusted_fields_and_exact_entries() -> None:
    rows = json.loads((ROOT.parent / "config/admission-sources.json").read_text("utf-8"))
    sources = load_sources()
    assert len(rows) == len(sources) == 121
    audit = json.loads((ROOT.parent / "docs/admission-source-catalog-2026-11-01.json").read_text())
    assert {row["name"] for row in rows} == {row["schoolName"] for row in audit["schools"]}
    for row in rows:
        assert set(row) == {"code", "name", "hosts", "entries", "year"}
        source = sources[row["code"]]
        assert source.entries == row["entries"]
        assert source.name == row["name"]
        assert source.year == row["year"]
        assert source.hosts == row["hosts"]


def test_exact_contract_rejects_extra_fields_and_unknown_codes() -> None:
    for changes in ({"url": "https://evil.example"}, {"year": 2027}):
        with pytest.raises(ValidationError):
            query(**changes)
    with pytest.raises(ValueError):
        AdmissionLinksRegistry().get(query("unknown"))
    value = AdmissionLinksRegistry().get(query()).model_dump(mode="json")
    assert set(value) == {"schoolCode", "schoolName", "registeredYear", "entryUrls"}
    with pytest.raises(ValueError):
        checked_size({"body": "字" * 65536})


def test_deterministic_routing_examples_and_guards() -> None:
    for text, code in (
        ("查官网南京审计大学", "nau"),
        ("南京审计大学查官网", "nau"),
        ("帮我查询北京航空航天大学招生信息", "buaa"),
        ("给我南京审计大学招生网址", "nau"),
        ("核对南京审计大学招生信息", "nau"),
        ("帮我查询北京大学的招生信息", "pku"),
        ("给我清华大学招生网址", "thu"),
    ):
        plan = admission_links_plan(conversation(text))
        assert plan is not None and plan.action == "ADMISSION_LINKS"
        assert plan.clarification is None
        assert plan.admissionLinks is not None and plan.admissionLinks.schoolCode == code
    assert not admission_requested("推荐南京审计大学")
    mixed = admission_links_plan(conversation("推荐南京审计大学并给我招生网址"))
    assert mixed is not None and mixed.action == "ADMISSION_LINKS" and mixed.admissionLinks is not None
    assert mixed.admissionLinks.schoolCode == "nau"
    assert not admission_requested("不要查官网南京审计大学")
    assert not admission_requested("示例：查询南京审计大学招生信息")
    assert not admission_requested("如何使用查官网功能")
    assert admission_scope_requested("你可以查询哪些学校官网")
    assert not admission_requested("你可以查询哪些学校官网")


def test_missing_multiple_and_unknown_schools_clarify_without_year_or_major() -> None:
    for text in ("查官网", "帮我查询未登记测试大学招生信息", "查官网南京审计大学和北京航空航天大学"):
        plan = admission_links_plan(conversation(text))
        assert plan is not None and plan.action == "ADMISSION_LINKS"
        assert plan.admissionLinks is None
        assert plan.clarification
        assert "年份" not in plan.clarification
        assert "专业" not in plan.clarification
    names = [name for name, _ in explicit_schools("查官网南京审计大学和北京航空航天大学")]
    assert names == ["南京审计大学", "北京航空航天大学"]


@pytest.mark.parametrize("source", list(load_sources().values()), ids=lambda source: source.code)
def test_all_registered_schools_route_without_model_or_missing_conditions(source: AdmissionSource) -> None:
    """Every catalog institution must have one deterministic school-code route."""
    for name in (source.name, source.name.replace("（", "(").replace("）", ")")):
        plan = admission_links_plan(conversation(f"帮我查询{name}的招生信息"))
        assert plan is not None and plan.clarification is None
        assert plan.admissionLinks is not None and plan.admissionLinks.schoolCode == source.code


def test_overlapping_school_names_do_not_hide_a_second_explicit_school() -> None:
    """A long institution name is one school; separate mentions remain multiple."""
    for text in (
        "查官网中国矿业大学（北京）和中国矿业大学",
        "查官网中国矿业大学和中国矿业大学(北京)",
    ):
        plan = admission_links_plan(conversation(text))
        assert plan is not None and plan.admissionLinks is None and plan.clarification


def test_large_scope_answer_and_clarifications_stay_within_wire_limits() -> None:
    """Full catalog and bounded guidance fit Java result and plan constraints."""
    answer = admission_source_answer()
    assert "121所" in answer and len(answer) <= 20000
    for source in load_sources().values():
        assert source.name in answer
        assert all(url in answer for url in source.entries)
    for text in ("查官网", "查官网未登记测试大学"):
        plan = admission_links_plan(conversation(text))
        assert plan is not None and plan.clarification and len(plan.clarification) <= 1000
        assert "你可以查询哪些学校官网" in plan.clarification


def test_model_plans_cannot_generate_admission_links_even_with_old_action() -> None:
    plan = ModelConversationResolution.model_validate({
        "action": "ADMISSION_CHECK",
        "admissionCheck": {"schoolCode": "nau", "year": 2027, "majorCode": "081200"},
        "standaloneQuery": "查官网南京审计大学",
    })
    assert plan.action == "CHAT" and plan.admissionLinks is None and plan.clarification
    plan = ModelConversationResolution.model_validate({
        "action": "CHAT",
        "admissionLinks": {"schoolCode": "nau"},
        "standaloneQuery": "查官网南京审计大学",
    })
    assert plan.action == "CHAT" and plan.admissionLinks is None and plan.clarification
    legacy = conversation("查官网南京审计大学", preparedPlan={
        "action": "ADMISSION_CHECK",
        "admissionCheck": {"schoolCode": "nau", "year": 2027, "majorCode": "081200"},
        "standaloneQuery": "查官网南京审计大学",
    })
    assert legacy.preparedPlan is not None and legacy.preparedPlan.action == "CHAT"
    with pytest.raises(ValidationError):
        ConversationResolution(action="ADMISSION_CHECK", standaloneQuery="旧计划")


@pytest.mark.asyncio
async def test_real_stdio_catalog_annotations_exact_result_and_rejections() -> None:
    client = McpAdmissionClient()
    assert isinstance(AdmissionLinksTool(client), Tool)
    assert set(client.server_parameters().env) == {
        "KAOYAN_ADMISSION_CONFIG", "PYTHON_DOTENV_DISABLED", "PYTHONUNBUFFERED",
    }
    async with client.connect():
        assert client.session is not None
        catalog = await client.session.list_tools()
        assert catalog.nextCursor is None and len(catalog.tools) == 1
        tool = catalog.tools[0]
        assert tool.name == TOOL_NAME
        assert tool.inputSchema == AdmissionLinksQuery.model_json_schema()
        assert tool.outputSchema == AdmissionLinksResult.model_json_schema()
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.idempotentHint is True
        assert tool.annotations.openWorldHint is False
        assert tool.annotations.destructiveHint is False
        result = await client.check(**query().model_dump())
        assert result == {
            "schoolCode": "nau",
            "schoolName": "南京审计大学",
            "registeredYear": 2027,
            "entryUrls": list(load_sources()["nau"].entries),
        }
        for arguments in (
            {"schoolCode": "unknown"},
            {"schoolCode": "nau", "year": 2027},
            {"schoolCode": "nau", "url": "https://evil.example"},
        ):
            rejected = await client.session.call_tool(TOOL_NAME, arguments)
            assert rejected.isError
        other = await client.session.call_tool("check_admission_updates", {"schoolCode": "nau"})
        assert other.isError


@pytest.mark.asyncio
async def test_forged_or_mutated_link_result_is_rejected(tmp_path: Path) -> None:
    client = McpAdmissionClient()
    original = client.server_parameters()
    client.server_parameters = lambda: original.model_copy(update={
        "args": ["-m", "tests.mcp_runtime_probe"],
        "env": {**original.env, "RUNTIME_PROBE_EVENTS": str(tmp_path / "events"), "RUNTIME_PROBE_MODE": "forged"},
    })
    async with client.connect():
        with pytest.raises(McpCallError) as caught:
            await client.check(**query().model_dump())
        assert caught.value.code == McpErrorCode.RESULT_INVALID


@pytest.mark.asyncio
async def test_actual_mcp_child_has_sockets_and_parser_imports_blocked(tmp_path: Path) -> None:
    """The real child still returns links with socket, HTTP and parser guards installed."""
    events = tmp_path / "guard"
    client = McpAdmissionClient()
    original = client.server_parameters()
    client.server_parameters = lambda: original.model_copy(update={
        "env": {
            **original.env,
            "PYTHONPATH": str(NO_NETWORK),
            "ADMISSION_NETWORK_GUARD_EVENTS": str(events),
        },
    })
    async with client.connect():
        result = await client.check(**query().model_dump())
    assert result["entryUrls"] == list(load_sources()["nau"].entries)
    assert events.read_text("utf-8").splitlines() == ["guarded"]


@pytest.mark.asyncio
async def test_offline_script_reads_config_without_network_or_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = ROOT.parent / "scripts/check-admission.py"
    spec = importlib.util.spec_from_file_location("check_admission_offline", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    def forbidden(*args: object, **kwargs: object) -> None:
        """Any socket construction means the offline check is not offline."""
        raise AssertionError("offline admission check attempted network access")

    monkeypatch.setattr(socket, "socket", forbidden)
    report = await module.inspect(False, "nau")
    assert report["mode"] == "offline"
    assert report["schools"] == 1
    assert report["results"][0]["entryUrls"] == list(load_sources()["nau"].entries)


@pytest.mark.asyncio
async def test_mcp_script_uses_real_local_protocol_and_rejects_old_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = ROOT.parent / "scripts/check-admission.py"
    spec = importlib.util.spec_from_file_location("check_admission_mcp", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    report = await module.inspect(True, "nau")
    assert report["mode"] == "mcp"
    assert report["mcpStatus"]["state"] == "READY"
    assert report["results"][0]["status"] == "OK"
    for old in (["--live"], ["--transport", "local"]):
        monkeypatch.setattr(sys, "argv", ["check-admission.py", *old])
        with pytest.raises(SystemExit):
            module.main()


def test_disabled_or_failed_mcp_is_unsupported_without_local_fallback() -> None:
    app = create_app(settings(ADMISSION_MCP_ENABLED=False), model=FakeModel(error=True))
    body = request("CHAT", userInput="查官网南京审计大学")
    with TestClient(app) as http:
        plan = http.post("/internal/rag/conversation/plan", headers=HEADERS, json=body).json()
        assert plan["action"] == "ADMISSION_LINKS"
        assert plan["admissionLinks"] == {"schoolCode": "nau"}
        response = http.post(
            "/internal/rag/conversation/stream",
            headers=HEADERS,
            json={**body, "preparedPlan": plan},
        )
        assert '"type": "result"' in response.text
        assert '"outcome": "UNSUPPORTED"' in response.text
        assert "尚未启用" in response.text
        assert '"admissionLinks"' not in response.text
        assert '"admissionCheck"' not in response.text


@pytest.mark.parametrize("code", ["nau", "pku", "cumtb", "zju"])
def test_enabled_mcp_returns_links_and_never_emits_admission_check(code: str) -> None:
    """New institutions complete the actual FastAPI/SSE/stdio path without a model."""
    app = create_app(settings(ADMISSION_MCP_ENABLED=True), model=FakeModel(error=True))
    source = load_sources()[code]
    body = request("CHAT", userInput=f"给我{source.name}招生官网链接")
    with TestClient(app) as http:
        plan = http.post("/internal/rag/conversation/plan", headers=HEADERS, json=body).json()
        response = http.post(
            "/internal/rag/conversation/stream",
            headers=HEADERS,
            json={**body, "preparedPlan": plan},
        )
        assert '"type": "result"' in response.text
        assert '"outcome": "COMPLETED"' in response.text
        assert f'"schoolCode": "{code}"' in response.text
        assert '"registeredYear": 2027' in response.text
        assert '"admissionCheck"' not in response.text
