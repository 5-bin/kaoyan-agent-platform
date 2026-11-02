"""Check the local admission link registry, optionally over the real stdio MCP."""

import argparse
import asyncio
import json
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kaoyan-agent"))

from core.admission_client import McpAdmissionClient
from core.admission_contract import TOOL_NAME, load_sources
from core.mcp_runtime import McpCallError
from core.runtime import CallBudget, admission_budget
from schemas import AdmissionLinksQuery


async def inspect(mcp: bool = False, school: str | None = None) -> dict[str, object]:
    """Validate configuration offline or exercise one real local stdio link lookup."""
    sources = load_sources()
    if school is not None:
        if school not in sources:
            raise ValueError("Unknown school code")
        sources = {school: sources[school]}
    results: list[dict[str, object]] = []
    report: dict[str, object] = {
        "mode": "mcp" if mcp else "offline",
        "tool": TOOL_NAME,
        "schools": len(sources),
        "results": results,
    }
    if not mcp:
        for source in sources.values():
            results.append({
                "schoolCode": source.code,
                "schoolName": source.name,
                "registeredYear": source.year,
                "entryUrls": list(source.entries),
            })
        return report
    async with AsyncExitStack() as stack:
        client = McpAdmissionClient()
        await stack.enter_async_context(client.connect(isolate_failure=True))
        for source in sources.values():
            query = AdmissionLinksQuery(schoolCode=source.code)
            started = monotonic()
            token = admission_budget.set(CallBudget(1))
            try:
                value = await client.check(**query.model_dump())
                expected = {
                    "schoolCode": source.code,
                    "schoolName": source.name,
                    "registeredYear": source.year,
                    "entryUrls": list(source.entries),
                }
                if value != expected:
                    raise ValueError("ADMISSION_LINKS_MISMATCH")
                value["status"] = "OK"
            except McpCallError as error:
                value = {"status": "UNAVAILABLE", "errorCode": error.code.value}
            except (TimeoutError, ValueError):
                value = {
                    "status": "UNAVAILABLE",
                    "errorCode": "RESULT_INVALID",
                }
            finally:
                admission_budget.reset(token)
            value["school"] = source.name
            value["elapsedMs"] = round((monotonic() - started) * 1000)
            results.append(value)
            print(source.code + ": " + str(value["status"]), flush=True)
        report["mcpStatus"] = client.status.snapshot()
    if any(item["status"] != "OK" for item in results):
        raise ValueError("ADMISSION_LINK_SMOKE_FAILED")
    return report


def main() -> None:
    """Print the offline registry by default; --mcp explicitly starts real stdio."""
    parser = argparse.ArgumentParser(
        description=__doc__, allow_abbrev=False
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Exercise the real local stdio MCP; no network, model or business records",
    )
    parser.add_argument(
        "--school",
        choices=sorted(load_sources()),
        help="Check only one registered school code",
    )
    parser.add_argument("--output", type=Path, help="Write one new JSON report")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error("output must not already exist")
    report = asyncio.run(inspect(args.mcp, args.school))
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output is not None:
        with args.output.open("x", encoding="utf-8") as target:
            target.write(encoded + "\n")
    else:
        print(encoded)


if __name__ == "__main__":
    main()
