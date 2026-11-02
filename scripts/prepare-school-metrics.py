"""Prepare a complete, source-backed catalog enrichment plan without database writes.

Inputs are a read-only catalog snapshot, the original workbook, saved public
research receipts, independently reviewed observations and classification facts.
This command does not execute workbook cells, fetch web pages or call models.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from school_metrics import Context, Entry, Manifest, Observation, SchoolChange, Source, Target, digest, select_metric

ROOT = Path(__file__).resolve().parents[1]


def workbook_identities(path: Path) -> dict[str, set[str]]:
    """Read only source/school/program IDs from XLSX XML, preserving the original file."""
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    result: dict[str, set[str]] = {}
    with zipfile.ZipFile(path) as book:
        strings = ["".join(node.itertext()) for node in ET.fromstring(book.read("xl/sharedStrings.xml")).findall("s:si", ns)] if "xl/sharedStrings.xml" in book.namelist() else []
        relations = {r.get("Id"): r.get("Target") for r in ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))}
        for sheet in ET.fromstring(book.read("xl/workbook.xml")).findall("s:sheets/s:sheet", ns):
            name = sheet.get("name")
            if name not in ("来源", "院校", "招生专业"):
                continue
            identifier = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = relations[identifier]
            location = target.lstrip("/") if target.startswith("/") else "xl/" + target
            result[name] = set()
            for row in ET.fromstring(book.read(location)).findall("s:sheetData/s:row", ns):
                if int(row.get("r", "0")) < 3:
                    continue
                cell = next((c for c in row.findall("s:c", ns) if re.fullmatch(r"A\d+", c.get("r", ""))), None)
                if cell is None:
                    continue
                value = cell.find("s:v", ns)
                text = value.text if value is not None else ""
                if cell.get("t") == "s" and text:
                    text = strings[int(text)]
                elif cell.get("t") == "inlineStr":
                    text = "".join(cell.find("s:is", ns).itertext())
                if text:
                    result[name].add(text)
    return result


def targets(catalog: dict[str, object], fixtures: dict[str, object]) -> list[Target]:
    """Restore 782 mapped collection scopes and the original source-backed programs."""
    schools = {r["id"]: r for r in catalog["schools"]}
    fields: dict[int, dict[str, object]] = {}
    for row in catalog["staged"]:
        if row["record_type"] == "招生专业":
            payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
            if row["target_table"] != "school_detail" or row["target_id"] in fields:
                raise ValueError("招生专业映射缺失或重复")
            fields[row["target_id"]] = payload["fields"]
    result = []
    for row in catalog["details"]:
        school = schools[row["school_id"]]
        original = fields.get(row["id"])
        if original is None:
            matches = [p for p in fixtures["programs"] if p["school"] == school["name"]
                       and p["majorCode"] == row["major_code"] and p["year"] == row["year"]]
            if len(matches) != 1:
                raise ValueError("原专业快照不能唯一恢复")
            original = matches[0]
        context = Context(college=original.get("college", ""), track=original.get("track", ""),
                          studyMode=original.get("studyMode", ""), admissionCategory=original.get("admissionCategory", "ordinary"))
        result.append(Target(detailId=row["id"], schoolId=school["id"], school=school["name"],
                             majorCode=row["major_code"], year=row["year"], context=context))
    return result


def research_sources(path: Path) -> dict[tuple[int, str], list[Source]]:
    """Read Exa search receipts; snippets are discovery evidence, not numeric facts."""
    result: dict[tuple[int, str], list[Source]] = {}
    for file in path.glob("*-*.json"):
        record = json.loads(file.read_text())
        if record["result"].get("isError"):
            raise ValueError("存在未完成的搜索，不能标记查证完成：" + file.name)
        text = "\n".join(c.get("text", "") for c in record["result"].get("content", []) if c.get("type") == "text")
        sources = []
        for block in re.split(r"(?m)(?=^Title: )", text):
            title = re.search(r"(?m)^Title: (.+)", block)
            url = re.search(r"(?m)^URL: (https://\S+)", block)
            if not title or not url:
                continue
            address = url.group(1)
            sources.append(Source(title=title.group(1).strip()[:500], url=address,
                                  locator="本轮候选来源检索；仅作为查证入口，未从搜索摘要推定数值。",
                                  retrievedAt=date.today(), sourceType="OFFICIAL" if re.match(r"https://[^/]+\.(edu|ac)\.cn/", address) else "THIRD_PARTY"))
        # Leave unrelated search hits in private receipts; their presence does not certify a source.
        same_school = [s for s in sources if record["school"] in s.title]
        result[(record["schoolId"], record["kind"])] = same_school[:5]
    return result


def prepare(catalog_path: Path, workbook: Path, research_path: Path,
            observations_path: Path, levels_path: Path, output: Path) -> Manifest:
    """Produce immutable JSON/CSV and a human-readable preview for every row."""
    if output.exists():
        raise ValueError("输出目录已存在，拒绝覆盖")
    catalog = json.loads(catalog_path.read_text())
    fixture = json.loads((ROOT / "scripts/fixtures/feature-2027-schools.json").read_text())
    identities = workbook_identities(workbook)
    for kind, expected in identities.items():
        staged = {r["external_id"] for r in catalog["staged"] if r["record_type"] == kind}
        if not expected.issubset(staged):
            raise ValueError("工作簿记录未完整映射到已有采集包：" + kind)
    rows = targets(catalog, fixture)
    observations = [Observation.model_validate(value) for value in json.loads(observations_path.read_text())]
    schools = [SchoolChange.model_validate(value) for value in json.loads(levels_path.read_text())]
    research = research_sources(research_path)
    for school in schools:
        if any((school.school_id, kind) not in research for kind in ("ENROLLMENT", "CUTOFF_REFERENCE")):
            raise ValueError("院校未完成两类检索：" + school.name)
    entries = [Entry(target=target,
                     enrollment=select_metric(target, "ENROLLMENT", observations, research[(target.school_id, "ENROLLMENT")]),
                     cutoffReference=select_metric(target, "CUTOFF_REFERENCE", observations, research[(target.school_id, "CUTOFF_REFERENCE")]))
               for target in rows]
    data = {"format": "school-metrics-v1", "database": catalog["database"], "checkedAt": date.today().isoformat(),
            "workbookSha256": hashlib.sha256(workbook.read_bytes()).hexdigest(), "catalogFingerprints": catalog["fingerprints"],
            "schools": [s.model_dump(mode="json", by_alias=True) for s in schools],
            "entries": [e.model_dump(mode="json", by_alias=True) for e in entries],
            "research": {str(s.school_id): [str(p.resolve().relative_to(ROOT)) for p in sorted(research_path.glob(f"{s.school_id}-*.json"))] for s in schools}}
    data["manifestSha256"] = digest(data)
    manifest = Manifest.model_validate(data)
    output.mkdir(parents=True)
    (output / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    with (output / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["专业ID", "学校", "学院", "专业代码", "方向", "学习方式", "招考类别", "指标", "指标年份", "数值", "状态", "口径", "共用范围标识", "范围说明", "查证说明", "来源"])
        for entry in entries:
            target = entry.target
            for kind, metric in (("招生计划", entry.enrollment), ("复试参考线", entry.cutoff_reference)):
                writer.writerow([target.detail_id, target.school, target.context.college, target.major_code,
                                 target.context.track, target.context.study_mode, target.context.admission_category,
                                 kind, metric.year, metric.value, metric.status, metric.basis, metric.scope_key,
                                 metric.scope_label, metric.notice, "；".join(s.url for s in metric.sources)])
    with (output / "school-levels.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["院校ID", "学校", "原层次", "核对层次", "依据", "来源"])
        writer.writerows([s.school_id, s.name, s.old_level, s.level, s.evidence_note, "；".join(v.url for v in s.sources)] for s in schools)
    statuses = {kind: dict(Counter(getattr(e, kind).status for e in entries)) for kind in ("enrollment", "cutoff_reference")}
    summary = {"schools": len(schools), "programs": len(entries), "levelChanges": sum(s.old_level != s.level for s in schools),
               "levels": dict(Counter(s.level for s in schools)), "statuses": statuses, "manifestSha256": manifest.manifest_sha256}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    lines = ["# 院校数据补齐预览", "", "**仅准备清单，尚未写入日常库，也未重启服务。**", "",
             f"核对{len(schools)}所院校、{len(entries)}条专业；层次拟更新{summary['levelChanges']}所。", "",
             "| 指标 | 官方数值 | 第三方待核实 | 范围不匹配 | 未找到可靠来源 | 冲突 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for kind, label in (("enrollment", "2027招生计划"), ("cutoff_reference", "往年复试线")):
        counts = statuses[kind]
        lines.append("| " + label + " | " + " | ".join(str(counts.get(key, 0)) for key in ("OFFICIAL", "UNVERIFIED", "SCOPE_MISMATCH", "NOT_FOUND", "CONFLICT")) + " |")
    lines += ["", "专业行数量不是独立计划数；相同共用范围标识不得累计。未取得数字的记录不代表学校未公布。",
              "", "逐条结果：[metrics.csv](metrics.csv)；层次及教育部依据：[school-levels.csv](school-levels.csv)；完整校验清单：[manifest.json](manifest.json)。",
              "", "拟新增V14指标表，每个专业两项；更新院校层次。原专业人数、分数线、备注和采集payload保持原值，个人记录及RAG不变。",
              "写库前完成完整备份、独立恢复与失败／重复导入预演；DDL独立提交，若后续数据事务失败，可能保留空指标表。",
              "恢复依据私密备份和导入摘要逐行撤销；不整库覆盖后续用户数据。",
              "", "清单SHA-256：`" + manifest.manifest_sha256 + "`。"]
    (output / "preview.md").write_text("\n".join(lines) + "\n")
    write_review_reports(manifest, output)
    for source, name in ((observations_path, "reviewed-observations.json"), (levels_path, "reviewed-levels.json")):
        (output / name).write_bytes(source.read_bytes())
    return manifest


def write_review_reports(manifest: Manifest, output: Path) -> None:
    """Deliver source locations, per-school coverage and every unresolved scope."""
    sources = {digest(s.model_dump(mode="json", by_alias=True)): s
               for school in manifest.schools for s in school.sources}
    for entry in manifest.entries:
        for metric in (entry.enrollment, entry.cutoff_reference):
            for source in metric.sources:
                sources[digest(source.model_dump(mode="json", by_alias=True))] = source
    with (output / "sources.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["来源标识", "标题", "链接", "原文位置", "获取日期", "来源类型"])
        for identity, source in sorted(sources.items()):
            writer.writerow([identity, source.title, source.url, source.locator, source.retrieved_at, source.source_type])
    with (output / "gaps.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["专业ID", "学校", "学院", "专业代码", "方向", "学习方式", "招考类别", "指标", "状态", "说明", "候选来源"])
        for entry in manifest.entries:
            target = entry.target
            for kind, metric in (("招生计划", entry.enrollment), ("复试参考线", entry.cutoff_reference)):
                if metric.value is None:
                    writer.writerow([target.detail_id, target.school, target.context.college, target.major_code,
                                     target.context.track, target.context.study_mode, target.context.admission_category,
                                     kind, metric.status, metric.notice, "；".join(s.url for s in metric.sources)])
    lines = ["# 院校逐校处理与缺口报告", "", "未找到数值不等于学校未公布。每条缺口的学院、方向、方式及候选来源见[gaps.csv](gaps.csv)。",
             "所有统计按数据库专业记录计数；各方向共用的同一计划不重复累计人数。", "",
             "| 学校 | 层次 | 专业记录 | 有计划数值 | 有参考线数值 |", "| --- | --- | ---: | ---: | ---: |"]
    for school in manifest.schools:
        entries = [e for e in manifest.entries if e.target.school_id == school.school_id]
        lines.append(f"| {school.name} | {school.level} | {len(entries)} | "
                     f"{sum(e.enrollment.value is not None for e in entries)} | "
                     f"{sum(e.cutoff_reference.value is not None for e in entries)} |")
    lines += ["", "本轮未将缺口推定为“未公布”，也未将录取最低分、专项线或不同学院数值代填。",
              "官方来源状态表示来源及范围核对，不代表招生部门或小组人工审核已完成。",
              "第三方数值独立标为待核实，不进入学情历史指标、条件推荐或RAG审核资料。",
              "原Excel、采集payload及15条原始专业资料未被覆盖；新增上下文仅用于详情展示。",
              "", "[来源及原文定位](sources.csv) · [逐条处理结果](metrics.csv) · [完整清单](manifest.json)"]
    (output / "gaps.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    """Require explicit source files and a new output directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("catalog", "workbook", "research", "observations", "levels", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare(args.catalog, args.workbook, args.research, args.observations, args.levels, args.output)
    print(json.dumps({"schools": len(manifest.schools), "programs": len(manifest.entries),
                      "manifestSha256": manifest.manifest_sha256}, ensure_ascii=False))


if __name__ == "__main__":
    main()
