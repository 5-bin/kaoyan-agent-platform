#!/usr/bin/env python3
"""Frozen quality evaluation for the internal Agent contract.

Default mode is offline: the model is disabled and only deterministic
retrieval/rules are measured. ``--model`` uses the root .env configuration and
therefore creates real provider requests; use ``--only``/``--limit`` to cap it.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kaoyan-agent"))

from fastapi.testclient import TestClient  # noqa: E402

from config import Settings, provider_identifier  # noqa: E402
from main import create_app  # noqa: E402

INTERNAL_KEY = "eval-only-internal-key-123456"
HEADERS = {"X-Internal-Key": INTERNAL_KEY}


def load_cases(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def body_for(case: dict, *, model_enabled: bool, provider: str) -> dict:
    return {
        "taskId": "eval-" + case["id"],
        "userId": 1,
        "taskType": case["taskType"],
        "userInput": case["userInput"],
        "profile": case.get("profile", {}),
        "preferences": case.get("preferences", {}),
        "privacy": {
            "modelAllowed": model_enabled,
            "scopes": ["profile"] if model_enabled else [],
            "provider": provider if model_enabled else None,
        },
    }


def evaluate(case: dict, response: dict, *, model_enabled: bool) -> dict:
    result = response.get("result") or {}
    references = response.get("references") or result.get("references") or []
    candidates = result.get("candidates") or []
    expect = case.get("expect", {})
    answer = str(result.get("answer", ""))
    reference_ids = [str(item.get("id", "")) for item in references]
    candidate_ids = [str(item.get("programId", "")) for item in candidates]

    outcome_ok = result.get("outcome") == expect.get("outcome")
    reference_ok = None
    if expect.get("referencePrefix"):
        reference_ok = any(value.startswith(expect["referencePrefix"]) for value in reference_ids)
    candidate_ok = None
    if expect.get("candidatePrefix"):
        candidate_ok = any(value.startswith(expect["candidatePrefix"]) for value in candidate_ids)
    must_not_ok = None
    if expect.get("mustNotContain"):
        must_not_ok = expect["mustNotContain"] not in answer

    checks = [value for value in (outcome_ok, reference_ok, candidate_ok, must_not_ok) if value is not None]
    support = result.get("citationSupport") or {}
    return {
        "id": case["id"],
        "taskType": case["taskType"],
        "input": case["userInput"],
        "outcome": result.get("outcome"),
        "expectedOutcome": expect.get("outcome"),
        "outcomeOk": outcome_ok,
        "referenceIds": reference_ids,
        "referenceOk": reference_ok,
        "candidateIds": candidate_ids,
        "candidateOk": candidate_ok,
        "explanationMode": result.get("explanationMode"),
        "citationSupport": support or None,
        "answerPreview": answer[:500],
        "notice": result.get("notice"),
        "passed": all(checks) if checks else outcome_ok,
        "modelEnabled": model_enabled,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(ROOT / "scripts/fixtures/quality-cases.json"))
    parser.add_argument("--output", default=None, help="报告路径；已存在时拒绝覆盖")
    parser.add_argument("--model", action="store_true", help="使用根 .env 的真实模型配置")
    parser.add_argument("--backend", choices=["lexical", "bm25", "qdrant", "hybrid"], default=None)
    parser.add_argument("--data", default=None, help="覆盖 RAG_DATA 语料路径")
    parser.add_argument("--only", default="", help="逗号分隔的 case id")
    parser.add_argument("--limit", type=int, default=0, help="最多执行前 N 个案例")
    args = parser.parse_args()

    overrides = {"AGENT_INTERNAL_KEY": INTERNAL_KEY}
    if not args.model:
        overrides["LLM_ENABLED"] = False
    if args.backend:
        overrides["RAG_BACKEND"] = args.backend
    if args.data:
        overrides["RAG_DATA"] = Path(args.data).resolve()
    settings = Settings(**overrides)

    if args.model and not settings.LLM_ENABLED:
        print("根 .env 未启用 LLM_ENABLED，无法使用 --model；先按 README 配置。", file=sys.stderr)
        return 2
    provider = provider_identifier(settings.LLM_BASE_URL)
    if args.model and provider == "unconfigured":
        print("LLM_BASE_URL 不是可用的 HTTPS 端点。", file=sys.stderr)
        return 2

    cases = load_cases(Path(args.cases))
    wanted = {value.strip() for value in args.only.split(",") if value.strip()}
    if wanted:
        cases = [case for case in cases if case["id"] in wanted]
    if args.limit > 0:
        cases = cases[:args.limit]
    if not cases:
        print("没有可执行的案例。", file=sys.stderr)
        return 2

    generated = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(args.output) if args.output else ROOT / ".cache" / f"quality-report-{generated}.json"
    if output.exists():
        print(f"报告已存在，拒绝覆盖：{output}", file=sys.stderr)
        return 2

    rows = []
    with TestClient(create_app(settings)) as client:
        for case in cases:
            response = client.post(
                "/internal/rag/chat",
                headers=HEADERS,
                json=body_for(case, model_enabled=args.model, provider=provider),
            )
            if response.status_code != 200:
                rows.append({"id": case["id"], "passed": False,
                             "error": f"http_{response.status_code}"})
                continue
            rows.append(evaluate(case, response.json(), model_enabled=args.model))

    passed = sum(1 for row in rows if row.get("passed"))
    reference_rows = [row for row in rows if row.get("referenceOk") is not None]
    candidate_rows = [row for row in rows if row.get("candidateOk") is not None]
    support_rows = [row for row in rows if row.get("citationSupport")]
    checked = sum(row["citationSupport"].get("checked", 0) for row in support_rows)
    supported = sum(row["citationSupport"].get("supported", 0) for row in support_rows)

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "mode": "model" if args.model else "offline",
        "backend": settings.RAG_BACKEND,
        "provider": provider if args.model else None,
        "corpus": str(settings.RAG_DATA),
        "summary": {
            "cases": len(rows),
            "passed": passed,
            "outcomeAccuracy": round(sum(1 for row in rows if row.get("outcomeOk")) / len(rows), 3),
            "referenceHitRate": round(sum(1 for row in reference_rows if row.get("referenceOk")) / len(reference_rows), 3)
            if reference_rows else None,
            "candidateHitRate": round(sum(1 for row in candidate_rows if row.get("candidateOk")) / len(candidate_rows), 3)
            if candidate_rows else None,
            "citationChecked": checked,
            "citationSupported": supported,
            "citationSupportRate": round(supported / checked, 3) if checked else None,
        },
        "cases": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"质量评测：{report['mode']} / {report['backend']} / {len(rows)} 例")
    print(f"{'case':<28}{'outcome':<14}{'ref':<6}{'candidate':<10}{'support':<12}pass")
    for row in rows:
        support = row.get("citationSupport") or {}
        print(f"{row['id']:<28}{str(row.get('outcome')):<14}{str(row.get('referenceOk')):<6}"
              f"{str(row.get('candidateOk')):<10}{support.get('status', '-'):<12}{row.get('passed')}")
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(f"报告：{output}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
