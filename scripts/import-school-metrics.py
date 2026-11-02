"""Preview or rehearse a bounded admission-metrics import; never starts services.

Default is read-only. --rehearse backs up kaoyan_dev and restores an isolated
copy. --apply requires the reviewed manifest SHA and repeats that rehearsal
before one guarded catalog transaction. The V14 DDL is additive and commits
separately; on a later import failure its empty table can remain.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parent))
from school_metrics import Manifest, canonical, database_values, digest, load_manifest

ROOT = Path(__file__).resolve().parents[1]
TABLE = "school_admission_metric"
MIGRATION = ROOT / "kaoyan-B/src/main/resources/db/V14__school_admission_metrics.sql"


def helpers() -> ModuleType:
    """Load existing local-MySQL/backup helpers without running their CLI."""
    spec = importlib.util.spec_from_file_location("school_import_helpers", ROOT / "scripts/import-real-data.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载数据库维护工具")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = helpers()
sql = helper.sql
require = helper.require


def expected_rows(manifest: Manifest) -> list[dict[str, object]]:
    """Project exactly two V14 rows per original catalog detail."""
    return [database_values(entry, kind) for entry in manifest.entries
            for kind in ("ENROLLMENT", "CUTOFF_REFERENCE")]


def normalize_saved(row: dict[str, object]) -> dict[str, object]:
    """Normalize MySQL JSON serialization before comparing a stored row."""
    result = {k: v for k, v in row.items() if k != "imported_at"}
    for field in ("context_json", "sources_json"):
        value = result[field]
        result[field] = canonical(json.loads(value) if isinstance(value, str) else value)
    return result


def inspect(db: object, manifest: Manifest) -> dict[str, object]:
    """Reject changed scopes and manual metric edits before any mutation."""
    require(db.name == "kaoyan_dev" or db.name.startswith("kaoyan_realdata_verify_"), "目标库不符")
    require(db.query("SELECT DISTINCT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE();") == "InnoDB",
            "存在非事务表，停止导入")
    schools = {r["id"]: r for r in db.records("school")}
    details = {r["id"]: r for r in db.records("school_detail")}
    require(set(schools) == {s.school_id for s in manifest.schools}, "院校集合改变，须重新准备清单")
    require(set(details) == {e.target.detail_id for e in manifest.entries}, "专业集合改变，须重新准备清单")
    for school in manifest.schools:
        saved = schools[school.school_id]
        require(saved["name"] == school.name and saved["level"] in (school.old_level, school.level), "院校名称或层次已被修改")
    for entry in manifest.entries:
        row, target = details[entry.target.detail_id], entry.target
        require((row["school_id"], row["major_code"], row["year"]) ==
                (target.school_id, target.major_code, target.year), "专业归属／年份改变")
    for table in ("school_detail", "collection_import_record"):
        require(db.fingerprint(table) == manifest.catalog_fingerprints[table], "原始采集或专业内容改变，须重新核对")
    wanted = {(r["school_detail_id"], r["metric_type"]): r for r in expected_rows(manifest)}
    saved = db.records(TABLE) if TABLE in db.tables() else []
    for record in saved:
        row = normalize_saved(record)
        identity = (row["school_detail_id"], row["metric_type"])
        if identity in wanted:
            require(row == wanted[identity], "已有指标与清单不同，禁止覆盖人工或其他批次修改")
    return {"database": db.name, "schoolsChecked": len(schools), "programsChecked": len(details),
            "schoolLevelsToChange": sum(schools[s.school_id]["level"] != s.level for s in manifest.schools),
            "metricsToInsert": len(wanted) - sum((r["school_detail_id"], r["metric_type"]) in wanted for r in saved),
            "metricStatuses": dict(Counter(r["status"] for r in wanted.values())),
            "requiresV14": TABLE not in db.tables(), "manifestSha256": manifest.manifest_sha256}


def ensure_schema(db: object) -> None:
    """Apply only V14 when absent and check its expected column set."""
    if TABLE not in db.tables():
        db.query(MIGRATION.read_text(encoding="utf-8"))
    columns = {"school_detail_id", "metric_type", "metric_year", "metric_value", "status", "scope_key",
               "scope_label", "basis", "context_json", "sources_json", "notice", "content_sha256", "imported_at"}
    require(set(db.columns(TABLE)) == columns, "V14表结构不符")


def statement(db: object, manifest: Manifest, before: dict[str, list[str]],
              rollback: bool = False, failure: bool = False) -> str:
    """Generate guarded SQL literals; source strings cannot become executable SQL."""
    lines = ["SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION';",
             "CREATE TEMPORARY TABLE admission_guard(v INT NOT NULL CHECK(v=1));",
             "INSERT INTO admission_guard VALUES(IF(GET_LOCK('kaoyan_school_metrics_v1',10)=1,1,0));",
             "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;", "START TRANSACTION;"]
    for table in ("school", "school_detail", "collection_import_record", TABLE):
        keys = db.keys(table)
        expression = db.fingerprint_expression(table)
        lines.append(f"SELECT {','.join(keys)} FROM `{table}` ORDER BY {','.join(keys)} FOR UPDATE;")
        lines.append(f"INSERT INTO admission_guard SELECT IF(COUNT(*)={len(before[table])},1,0) FROM `{table}`;")
        for fingerprint in before[table]:
            identity, checksum = fingerprint.split("\t")
            values = json.loads(identity)
            where = " AND ".join(f"`{key}`={sql(value)}" for key, value in zip(keys, values))
            lines.append(f"INSERT INTO admission_guard SELECT IF(COUNT(*)=1,1,0) FROM `{table}` WHERE {where} AND {expression}={sql(checksum)};")
    for school in manifest.schools:
        lines.append("UPDATE school SET level=" + sql(school.level) + " WHERE id=" + sql(school.school_id)
                     + " AND NOT(level <=> " + sql(school.level) + ");")
    for row in expected_rows(manifest):
        where = "school_detail_id=" + sql(row["school_detail_id"]) + " AND metric_type=" + sql(row["metric_type"])
        # Existing records were compared in full by inspect and locked above.
        lines.append("INSERT INTO `" + TABLE + "`(" + ",".join("`" + key + "`" for key in row)
                     + ") SELECT " + ",".join(sql(value) for value in row.values())
                     + " WHERE NOT EXISTS(SELECT 1 FROM `" + TABLE + "` WHERE " + where + ");")
    for row in expected_rows(manifest):
        matches = ["`" + field + "` <=> " + ("CAST(" + sql(value) + " AS JSON)" if field.endswith("_json") else sql(value))
                   for field, value in row.items()]
        lines.append("INSERT INTO admission_guard SELECT IF(COUNT(*)=1,1,0) FROM `" + TABLE
                     + "` WHERE " + " AND ".join(matches) + ";")
    if failure:
        lines.append("INSERT INTO admission_guard VALUES(0);")
    lines += ["ROLLBACK;" if rollback else "COMMIT;", "SELECT RELEASE_LOCK('kaoyan_school_metrics_v1');"]
    return "\n".join(lines) + "\n"


def verify(db: object, manifest: Manifest, before: dict[str, list[str]],
           original_schools: list[dict[str, object]]) -> dict[str, object]:
    """Verify every projected value and hash all unrelated tables without exposing rows."""
    after = db.snapshot()
    for table, fingerprints in before.items():
        if table not in ("school", TABLE):
            require(after[table] == fingerprints, "非目标表摘要发生变化：" + table)
    plan = inspect(db, manifest)
    require(plan["metricsToInsert"] == 0 and plan["schoolLevelsToChange"] == 0, "导入回读不完整")
    saved = {r["id"]: r for r in db.records("school")}
    wanted = {s.school_id: s.level for s in manifest.schools}
    for row in original_schools:
        allowed = {"level", "updated_at"} if row["level"] != wanted[row["id"]] else set()
        require(all(saved[row["id"]][key] == value for key, value in row.items() if key not in allowed),
                "院校非目标字段改变")
    return {"allMetricsReadBack": len(manifest.entries) * 2, "allSchoolsReadBack": len(manifest.schools),
            "nonTargetTableHashesUnchanged": True, "schoolOtherFieldsUnchanged": True, "legacyScoresUnchanged": True}


def run(manifest: Manifest, apply: bool = False) -> dict[str, object]:
    """Back up, restore, inject failures, test idempotence, then optionally apply."""
    db = helper.Database()
    preview = inspect(db, manifest)
    base = ROOT / ".cache/school-enrichment-20261101/operations"
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(base, 0o700)
    with (base / "operation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        output = base / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        output.mkdir(mode=0o700)
        before = db.snapshot()
        backup = db.backup(output)
        require(before == db.snapshot(), "备份期间数据变化，停止")
        name = "kaoyan_realdata_verify_" + secrets.token_hex(6)
        db.query(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4;", server=True)
        clone = helper.Database(name)
        clone.query(backup.read_text(), timeout=120)
        require(clone.snapshot() == before, "完整备份恢复摘要不一致")
        ensure_schema(clone)
        baseline = clone.snapshot()
        original_schools = clone.records("school")
        inspect(clone, manifest)
        try:
            clone.query(statement(clone, manifest, baseline, failure=True), timeout=120)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("失败注入未触发")
        require(clone.snapshot() == baseline, "失败事务未回滚")
        clone.query(statement(clone, manifest, baseline, rollback=True), timeout=120)
        require(clone.snapshot() == baseline, "显式回滚改变数据")
        clone.query(statement(clone, manifest, baseline), timeout=120)
        validation = verify(clone, manifest, baseline, original_schools)
        once = clone.snapshot()
        clone.query(statement(clone, manifest, once), timeout=120)
        require(clone.snapshot() == once, "重复执行并非幂等")
        original_metric = clone.records(TABLE)[0]
        identity = "school_detail_id=" + sql(original_metric["school_detail_id"]) + " AND metric_type=" + sql(original_metric["metric_type"])
        clone.query("UPDATE `" + TABLE + "` SET notice=" + sql("隔离测试人工修订") + " WHERE " + identity)
        edited = clone.snapshot()
        try:
            inspect(clone, manifest)
        except RuntimeError as error:
            require("禁止覆盖" in str(error), "人工修订拒绝原因不符")
        else:
            raise RuntimeError("人工修订未被保护")
        require(clone.snapshot() == edited, "预览改变了人工修订")
        clone.query("UPDATE `" + TABLE + "` SET notice=" + sql(original_metric["notice"]) + " WHERE " + identity)
        require(clone.snapshot() == once, "隔离人工修订夹具未恢复")
        report = {"applied": False, "preview": preview, "restoreDatabase": name,
                  "backup": str(backup), "backupRestoredTables": len(before),
                  "failureRollbackVerified": True, "explicitRollbackVerified": True,
                  "repeatUnchanged": True, "manualRevisionProtected": True, "validation": validation,
                  "migrationSha256": __import__("hashlib").sha256(MIGRATION.read_bytes()).hexdigest()}
        if apply:
            require(db.snapshot() == before, "预演期间日常数据变化，停止写入")
            inspect(db, manifest)
            ensure_schema(db)
            baseline = db.snapshot()
            original_schools = db.records("school")
            db.query(statement(db, manifest, baseline), timeout=120)
            report["validation"] = verify(db, manifest, baseline, original_schools)
            report["applied"] = True
        helper.dump(output / "report.json", report)
        report["reportPath"] = str(output / "report.json")
        return report


def main() -> None:
    """Expose explicit preview, rehearsal and checksum-bound apply modes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--rehearse", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-sha")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    if args.apply and args.expected_sha != manifest.manifest_sha256:
        parser.error("--apply必须提供已审阅清单的完整--expected-sha")
    result = run(manifest, args.apply) if args.rehearse or args.apply else inspect(helper.Database(), manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
