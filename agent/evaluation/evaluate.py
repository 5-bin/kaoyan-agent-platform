"""演示工程评估与真实模型对比入口；不导入即运行，不覆盖已有报告。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
from agent_service.model_client import ModelClient
from agent_service.runner import Runner
from agent_service.schemas import RunRequest
from agent_service.settings import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases.json"))
    parser.add_argument("--compare-model", action="store_true", help="定制与未定制模型对比")
    parser.add_argument("--allow-paid-calls", action="store_true", help="明确允许本次评估调用外部模型")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("报告已存在，请使用新的文件名")
    settings = Settings.from_env()
    if settings.mode == "model" and not args.allow_paid_calls:
        parser.error("模型模式可能产生费用，需要 --allow-paid-calls")
    if args.compare_model and settings.mode != "model":
        parser.error("定制前后对比需要真实模型模式")
    runner = Runner(settings)
    baseline = ModelClient(settings)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        result = runner.run(RunRequest(taskId=uuid4(), input=case["input"], taskType=case.get("taskType", "knowledge_qa")))
        checked = {"status": result.status == case["expectedStatus"],
                   "sources": {source.id for source in result.sources} == set(case["expectedSources"])}
        entry = {"case": case, "customized": result.model_dump(), "checks": checked}
        if args.compare_model:
            try:
                entry["baseline"] = baseline.generate({"input": case["input"]}, customized=False).model_dump()
            except Exception as error:
                entry["baseline"] = {"errorType": type(error).__name__}
        results.append(entry)
    report = {"createdAt": datetime.now(timezone.utc).isoformat(), "mode": settings.mode,
              "scope": "408工程演示案例，不是正式题库、领域准确率或真实用户调研", "model": settings.model_name or None,
              "baselinePolicy": "同一模型、相同输入、相同结构格式；基线不提供领域资料和工具，需人工按同一领域评分表评价",
              "cases": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
    print(f"已记录 {len(results)} 个案例；逐项检查通过 {sum(all(row['checks'].values()) for row in results)} 个。")


if __name__ == "__main__":
    main()
