"""Preview public-content merging or rehearse it in a disposable restored database.

No mode applies changes to the live database. Rehearsal uses local MySQL root
socket authentication; backups and generated SQL stay in a private directory.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
from typing import TypeAlias

from dotenv import dotenv_values

Json: TypeAlias = None | bool | int | float | str | list["Json"] | dict[str, "Json"]
Row: TypeAlias = dict[str, Json]
PUBLIC = ("school", "school_detail", "question", "document", "question_version", "school_admission_metric")
V13 = ("practice_session", "practice_session_item", "practice_request", "question_version",
       "learning_blueprint", "learning_profile", "learning_profile_history", "learning_event",
       "learning_recommendation_settings", "school_historical_metric")
JSON_FIELDS = {"snapshot_json", "context_json", "sources_json"}
VOLATILE = {"created_at", "updated_at", "reviewed_at", "imported_at"}
ACTORS = {"creator_user_id", "reviewer_user_id", "reviewer_id", "review_comment"}


def require(condition: object, message: str) -> None:
    """Reject an unsafe precondition without printing SQL or record contents."""
    if not condition:
        raise RuntimeError(message)


def canonical(value: object) -> str:
    """Serialize deterministic JSON for comparison and plan checksums."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: object) -> str:
    """Hash canonical UTF-8 JSON without exposing its contents."""
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def ident(value: str) -> str:
    """Quote a restricted SQL identifier; reject source-driven SQL syntax."""
    require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value), "非法SQL标识符")
    return "`" + value + "`"


def literal(value: Json) -> str:
    """Encode data as hexadecimal UTF-8 literals rather than executable text."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    require(not isinstance(value, float), "未定义浮点资料字段")
    text = value if isinstance(value, str) else canonical(value)
    return "CONVERT(0x" + text.encode().hex() + " USING utf8mb4)" if text else "''"


def detail_remark_key(value: Json, year: Json) -> Json:
    """Compare two observed 2027 display labels without rewriting saved facts."""
    prefix = "【2027官方来源核验摘要】"
    if year != 2027 or not isinstance(value, str) or not value.startswith(prefix):
        return value
    result = "【官方招生事实】" + value[len(prefix):]
    return re.sub(r"；核验：(\d{4}-\d{2}-\d{2})(?=；版本：)",
                  r"；核验日期：\1", result, count=1)


def normalized(row: Row, fields: list[str] | None = None) -> Row:
    """Normalize public JSON columns, excluding timestamps from comparisons."""
    result: Row = {}
    for key in fields if fields is not None else row:
        if key in VOLATILE:
            continue
        value = row.get(key)
        if key in JSON_FIELDS and isinstance(value, str):
            value = json.loads(value)
        if key == "remark":
            value = detail_remark_key(value, row.get("year"))
        result[key] = value
    return result


@dataclass
class Database:
    """Run bounded MySQL commands with credentials kept out of command arguments."""

    name: str
    options: list[str]
    environment: dict[str, str]

    def query(self, sql: str, *, server: bool = False, timeout: int = 120) -> str:
        """Execute caller-controlled maintenance SQL; redact all raw SQL errors."""
        command = ["mysql", "--no-defaults", "--connect-timeout=5", *self.options, "--batch", "--raw", "--skip-column-names"]
        if not server:
            command.append(self.name)
        result = subprocess.run(command, input="SET time_zone='+00:00';\n" + sql,
                                env=self.environment, text=True, capture_output=True, timeout=timeout)
        codes = re.findall(r"ERROR (\d+)", result.stderr)
        require(result.returncode == 0, "MySQL失败，错误编号=" + ",".join(codes))
        return result.stdout.strip()

    def tables(self) -> list[str]:
        """List table names without reading private record contents."""
        return self.query("SHOW TABLES;").splitlines()

    def columns(self, table: str) -> list[str]:
        """Read ordered schema metadata for one validated table name."""
        ident(table)
        return self.query("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE "
                          "TABLE_SCHEMA=DATABASE() AND TABLE_NAME=" + literal(table)
                          + " ORDER BY ORDINAL_POSITION;").splitlines()

    def keys(self, table: str) -> list[str]:
        """Read primary-key columns for guarded locking and fingerprint ordering."""
        return self.query("SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE "
                          "TABLE_SCHEMA=DATABASE() AND TABLE_NAME=" + literal(table)
                          + " AND CONSTRAINT_NAME='PRIMARY' ORDER BY ORDINAL_POSITION;").splitlines()

    def expression(self, table: str, columns: list[str] | None = None) -> str:
        """Build the same server-side row hash for preview and write guards."""
        fields = ",".join(ident(name) for name in (self.columns(table) if columns is None else columns))
        require(fields, "表结构缺失: " + table)
        return "SHA2(CAST(JSON_ARRAY(" + fields + ") AS CHAR),256)"

    def fingerprints(self, tables: list[str], columns: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
        """Return row hashes only, including private-table preservation evidence.

        Passing pre-migration columns keeps the comparison valid after additive columns.
        """
        result: dict[str, list[str]] = {}
        for table in tables:
            keys = self.keys(table)
            require(keys, "表缺少主键: " + table)
            fields = (columns or {}).get(table)
            result[table] = self.query("SELECT " + self.expression(table, fields) + " FROM " + ident(table)
                                       + " ORDER BY " + ",".join(map(ident, keys)) + ";").splitlines()
        return result

    def public_rows(self, table: str, fields: list[str]) -> list[Row]:
        """Read only explicitly exported public fields, excluding local actor IDs."""
        require(table in PUBLIC and not ACTORS.intersection(fields), "超出公共资料读取范围")
        require(set(fields).issubset(self.columns(table)), "公共表字段不兼容: " + table)
        pairs = ",".join(literal(name) + "," + ident(name) for name in fields)
        result = self.query("SELECT JSON_OBJECT(" + pairs + ") FROM " + ident(table)
                            + " ORDER BY " + ",".join(map(ident, self.keys(table))) + ";")
        return [json.loads(line) for line in result.splitlines() if line]


@dataclass
class Plan:
    """Explicit inserts, bounded school updates and preserved target permissions."""

    inserts: dict[str, list[Row]] = field(default_factory=lambda: {name: [] for name in PUBLIC})
    updates: list[Row] = field(default_factory=list)
    maps: dict[str, dict[int, int]] = field(default_factory=dict)
    reused: Counter[str] = field(default_factory=Counter)
    preserved_permissions: list[Row] = field(default_factory=list)
    permission_notes: dict[int, str] = field(default_factory=dict)
    enriched_snapshots: int = 0
    preserved_detail_remarks: list[Row] = field(default_factory=list)


def identity(table: str, row: Row) -> str:
    """Use content and institutional identities rather than local numeric IDs."""
    fields = {
        "school": ("name",),
        "school_detail": ("school_id", "major_name", "major_code", "year", "remark"),
        "question": ("subject", "content", "option_a", "option_b", "option_c", "option_d"),
        "document": ("title", "subject", "source_url"),
        "question_version": ("question_id", "version"),
        "school_admission_metric": ("school_detail_id", "metric_type"),
    }[table]
    values = [row.get(name) for name in fields]
    if table == "school_detail":
        values[-1] = detail_remark_key(row.get("remark"), row.get("year"))
    return canonical(values)


def diagnose_rows(table: str, source: list[Row], target: list[Row]) -> Row:
    """Report bounded public-field differences without changing merge policy."""
    require(table in ("question", "document"), "诊断范围仅为公开题目和资料")
    existing: dict[str, Row] = {}
    for saved in target:
        key = identity(table, saved)
        require(key not in existing, "服务器存在重复自然键: " + table)
        existing[key] = saved
    conflicts: list[Json] = []
    field_counts: Counter[str] = Counter()
    matched = 0
    for original in source:
        saved = existing.get(identity(table, original))
        if saved is None:
            continue
        matched += 1
        row = {**original, "id": saved["id"]}
        fields = [name for name in row if name != "stable_order"]
        before, after = normalized(saved, fields), normalized(row, fields)
        names = [name for name in before if before[name] != after[name]]
        if not names:
            continue
        field_counts.update(names)
        changes: Row = {}
        for name in names:
            require(name not in ACTORS, "拒绝输出审核账号字段")
            values: Row = {}
            for label, value in (("server", before[name]), ("local", after[name])):
                if isinstance(value, str):
                    values[label] = {"preview": value[:120], "length": len(value), "sha256": digest(value)}
                elif value is None or isinstance(value, (bool, int, float)):
                    values[label] = value
                else:
                    values[label] = {"sha256": digest(value), "type": type(value).__name__}
            changes[name] = values
        conflicts.append({"sourceId": original.get("id"), "serverId": saved.get("id"), "changes": changes})
    return {"table": table, "matched": matched, "newIdentities": len(source) - matched,
            "conflictingRows": len(conflicts), "changedFields": dict(field_counts), "examples": conflicts[:8]}


def build_plan(source: dict[str, list[Row]], target: dict[str, list[Row]]) -> Plan:
    """Map IDs, preserve existing records and reject conflicting question revisions."""
    require(set(source) == set(PUBLIC), "资料表白名单不符")
    plan = Plan()
    source_questions = {int(row["id"]): row for row in source["question"]}
    for table in PUBLIC:
        existing: dict[str, Row] = {}
        for row in target[table]:
            key = identity(table, row)
            require(key not in existing, "服务器存在重复自然键: " + table)
            existing[key] = row
        next_id = max((int(row["id"]) for row in target[table] if "id" in row), default=0) + 1
        mapping: dict[int, int] = {}
        source_keys: set[str] = set()
        for original in source[table]:
            require(not ACTORS.intersection(original), "资料混入审核账号字段")
            row = json.loads(canonical(original))
            if table == "school_detail":
                row["school_id"] = plan.maps["school"][int(row["school_id"])]
            elif table == "question_version":
                source_question_id = int(row["question_id"])
                row["question_id"] = plan.maps["question"][source_question_id]
                snapshot = row["snapshot_json"]
                if isinstance(snapshot, str):
                    snapshot = json.loads(snapshot)
                require(isinstance(snapshot, dict), "题目版本快照格式错误")
                require(not ({"user_id", "userId", "reviewer_user_id"} & snapshot.keys()), "快照混入账号字段")
                snapshot["id"] = row["question_id"]
                current = source_questions[source_question_id]
                # Only this newly imported current-version snapshot receives the
                # existing target notice. Older source versions remain unchanged.
                if (source_question_id in plan.permission_notes
                        and snapshot.get("permissionNote") == current.get("permission_note")
                        and snapshot.get("version") == current.get("version")
                        and row["version"] == current.get("version")):
                    snapshot["permissionNote"] = plan.permission_notes[source_question_id]
                    plan.enriched_snapshots += 1
                row["snapshot_json"] = snapshot
            elif table == "school_admission_metric":
                row["school_detail_id"] = plan.maps["school_detail"][int(row["school_detail_id"])]
                hashed = {key: value for key, value in row.items() if key not in ("content_sha256", "imported_at")}
                for name in ("context_json", "sources_json"):
                    value = hashed[name]
                    hashed[name] = canonical(json.loads(value) if isinstance(value, str) else value)
                row["content_sha256"] = digest(hashed)
            key = identity(table, row)
            require(key not in source_keys, "来源存在重复自然键: " + table)
            source_keys.add(key)
            saved = existing.get(key)
            if saved is not None:
                if "id" in original:
                    mapping[int(original["id"])] = int(saved["id"])
                    row["id"] = saved["id"]
                if table == "school":
                    changes = {name: row[name] for name in ("province", "level") if row[name] != saved[name]}
                    if changes:
                        plan.updates.append({"id": saved["id"], **changes})
                else:
                    fields = [name for name in row if name != "stable_order"]
                    before, after = normalized(saved, fields), normalized(row, fields)
                    changed = {name for name in before if before[name] != after[name]}
                    if table == "question" and changed == {"permission_note"}:
                        notice = saved.get("permission_note")
                        require(isinstance(notice, str) and notice.strip(), "服务器许可说明为空，需要人工核对")
                        source_id = int(original["id"])
                        plan.permission_notes[source_id] = notice
                        plan.preserved_permissions.append({
                            "sourceId": source_id, "serverId": saved["id"],
                            "serverNoticeSha256": digest(notice),
                            "sourceNoticeSha256": digest(row.get("permission_note")),
                        })
                    else:
                        require(not changed, "已有资料内容不同，禁止覆盖；表=" + table
                                + "；差异字段=" + ",".join(sorted(changed)))
                        if table == "school_detail" and saved.get("remark") != row.get("remark"):
                            plan.preserved_detail_remarks.append({
                                "sourceId": original["id"], "serverId": saved["id"],
                                "serverRemarkSha256": digest(saved.get("remark")),
                                "sourceRemarkSha256": digest(row.get("remark")),
                            })
                plan.reused[table] += 1
            else:
                if "id" in row:
                    mapping[int(original["id"])] = next_id
                    row["id"] = next_id
                    next_id += 1
                plan.inserts[table].append(row)
        plan.maps[table] = mapping
    return plan


V15_COLUMN = ("user", "degree_type")
V15_CONSTRAINT = "ck_user_degree_type"


def migrations(db: Database, release: Path) -> list[Path]:
    """Select only fully absent V13/V14/V15 groups; reject partial migrations."""
    tables = set(db.tables())
    for table, column in (("practice_record", "question_snapshot"), ("task", "deleted_at"),
                          ("question", "permission_note")):
        require(column in db.columns(table), "缺少V7/V8/V9前置字段")
    require({"chat_conversation", "chat_message", "chat_generation", "personal_document",
             "personal_document_version", "assistant_privacy", "assistant_action"}.issubset(tables),
            "缺少V10—V12前置表")
    present = tables.intersection(V13)
    require(not present or present == set(V13), "V13处于部分应用状态，禁止整份重跑")
    names = ([] if present else ["V13__learning_loop.sql"])
    if "school_admission_metric" not in tables:
        names.append("V14__school_admission_metrics.sql")
    # V15 adds one nullable column plus its CHECK; having only one of them is a manual partial state.
    has_column = V15_COLUMN[1] in db.columns(V15_COLUMN[0])
    has_check = db.query("SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=DATABASE() "
                         "AND TABLE_NAME=" + literal(V15_COLUMN[0]) + " AND CONSTRAINT_NAME="
                         + literal(V15_CONSTRAINT) + ";") == "1"
    require(has_column == has_check, "V15处于部分应用状态，禁止整份重跑")
    if not has_column:
        names.append("V15__profile_degree_type.sql")
    return [release / "kaoyan-B/src/main/resources/db" / name for name in names]


def transaction(db: Database, plan: Plan, before: dict[str, list[str]]) -> str:
    """Create guarded, transactional public-only inserts and school-field updates."""
    statements = ["SET NAMES utf8mb4;", "SET time_zone='+00:00';",
                  "SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION';",
                  "CREATE TEMPORARY TABLE kaoyan_deploy_guard(v INT NOT NULL CHECK(v=1));",
                  "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;", "START TRANSACTION;"]
    for table in PUBLIC:
        keys = ",".join(map(ident, db.keys(table)))
        statements.append("SELECT " + keys + " FROM " + ident(table) + " ORDER BY " + keys + " FOR UPDATE;")
        hashes = before.get(table, [])
        statements.append("INSERT INTO kaoyan_deploy_guard VALUES(IF((SELECT COUNT(*) FROM "
                          + ident(table) + ")=" + str(len(hashes)) + ",1,0));")
        if hashes:
            require(len(set(hashes)) == len(hashes), "重复行指纹")
            statements.append("INSERT INTO kaoyan_deploy_guard VALUES(IF((SELECT COUNT(*) FROM "
                              + ident(table) + " WHERE " + db.expression(table) + " IN ("
                              + ",".join(map(literal, hashes)) + "))=" + str(len(hashes)) + ",1,0));")
    for row in plan.updates:
        assignments = ",".join(ident(name) + "=" + literal(value) for name, value in row.items() if name != "id")
        statements.append("UPDATE school SET " + assignments + " WHERE id=" + literal(row["id"]) + ";")
    for table in PUBLIC:
        for row in plan.inserts[table]:
            statements.append("INSERT INTO " + ident(table) + " (" + ",".join(map(ident, row))
                              + ") VALUES (" + ",".join(literal(value) for value in row.values()) + ");")
    statements.append("COMMIT;")
    return "\n".join(statements) + "\n"


def inspect(db: Database, source: dict[str, list[Row]], release: Path) -> tuple[Plan, list[Path]]:
    """Read only public columns and choose migrations without executing them."""
    pending = migrations(db, release)
    tables = set(db.tables())
    target = {table: db.public_rows(table, list(source[table][0])) if table in tables else [] for table in PUBLIC}
    return build_plan(source, target), pending


def summary(plan: Plan, pending: list[Path], source_sha: str) -> Row:
    """Return a reviewable count-only plan bound to source, mappings and SQL files."""
    result: Row = {"sourceSha256": source_sha, "migrations": [path.name for path in pending],
                   "insertRows": {table: len(rows) for table, rows in plan.inserts.items()},
                   "reuseRows": dict(plan.reused), "schoolRowsToUpdate": len(plan.updates),
                   "questionPermissionNotesPreserved": len(plan.preserved_permissions),
                   "currentSnapshotsUsingPreservedNotes": plan.enriched_snapshots,
                   "schoolDetailDisplayLabelsPreserved": len(plan.preserved_detail_remarks),
                   "preserveAccountsAndPersonalRecords": True, "productionWritesPerformed": False}
    result["planSha256"] = digest({"summary": result, "inserts": plan.inserts, "updates": plan.updates,
                                   "preservedPermissions": plan.preserved_permissions,
                                   "preservedDetailRemarks": plan.preserved_detail_remarks,
                                   "migrations": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in pending}})
    return result


def rehearse(db: Database, source: dict[str, list[Row]], release: Path, output: Path, report: Row) -> None:
    """Back up live data, restore a new isolated DB, and validate merge and rollback."""
    require(output.is_dir(), "缺少私密输出目录")
    require(db.query("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() "
                     "AND (ENGINE<>'InnoDB' OR TABLE_TYPE<>'BASE TABLE');") == "0", "存在非InnoDB表或视图")
    for catalog in ("TRIGGERS", "ROUTINES", "EVENTS"):
        schema = "TRIGGER_SCHEMA" if catalog == "TRIGGERS" else "ROUTINE_SCHEMA" if catalog == "ROUTINES" else "EVENT_SCHEMA"
        require(db.query("SELECT COUNT(*) FROM information_schema." + catalog + " WHERE " + schema + "=DATABASE();") == "0",
                "存在自定义触发器、例程或事件，需要单独核对")
    backup = output / "server-before.sql"
    command = ["mysqldump", "--no-defaults", *db.options, "--single-transaction", "--no-tablespaces",
               "--set-gtid-purged=OFF", "--hex-blob", "--routines", "--events", "--triggers", db.name]
    with backup.open("xb") as stream:
        result = subprocess.run(command, env=db.environment, stdout=stream, stderr=subprocess.PIPE, timeout=180)
    details = result.stderr.decode(errors="replace")
    codes = re.findall(r"(?:ERROR\s+|Error:\s*)(\d+)", details)
    category = "UNSUPPORTED_OPTION" if "unknown variable" in details or "unknown option" in details else "MYSQL_ERROR"
    require(result.returncode == 0 and backup.stat().st_size > 0,
            "备份失败：" + category + "；exit=" + str(result.returncode)
            + "；错误编号=" + ",".join(codes) + "；未执行迁移")
    clone_name = "kaoyan_deploy_verify_" + secrets.token_hex(8)
    clone = Database(clone_name, db.options, db.environment)
    created = False
    try:
        db.query("CREATE DATABASE " + ident(clone_name) + " CHARACTER SET utf8mb4;", server=True)
        created = True
        clone.query(backup.read_text(), timeout=180)
        tables = clone.tables()
        baseline = clone.fingerprints(tables)
        private = {name: value for name, value in baseline.items() if name not in PUBLIC}
        # Additive migrations (V15) must not change existing personal columns.
        private_columns = {name: clone.columns(name) for name in private}
        plan, pending = inspect(clone, source, release)
        require(summary(plan, pending, str(report["sourceSha256"]))["planSha256"] == report["planSha256"],
                "备份时公共数据改变，请重新预览")
        for path in pending:
            clone.query(path.read_text())
        require(clone.fingerprints(list(private), private_columns) == private, "迁移改变了个人记录原有字段")
        if any(path.name.startswith("V15__") for path in pending):
            require(clone.query("SELECT COUNT(*) FROM " + ident(V15_COLUMN[0]) + " WHERE "
                                + ident(V15_COLUMN[1]) + " IS NOT NULL;") == "0", "V15新列应全部为空")
        sql = transaction(clone, plan, {name: value for name, value in baseline.items() if name in PUBLIC})
        (output / "public-merge.sql").write_text(sql)
        (output / "migrations.sql").write_text("\n".join(path.read_text() for path in pending))
        # Both an intentional error and an explicit rollback must leave all data unchanged.
        migrated = clone.fingerprints(clone.tables())
        try:
            clone.query(sql.removesuffix("COMMIT;\n") + "INSERT INTO kaoyan_deploy_guard VALUES(0);\nCOMMIT;\n")
        except RuntimeError:
            pass
        else:
            raise RuntimeError("故障注入没有中止事务")
        require(clone.fingerprints(clone.tables()) == migrated, "失败事务未完整回滚")
        clone.query(sql.removesuffix("COMMIT;\n") + "ROLLBACK;\n")
        require(clone.fingerprints(clone.tables()) == migrated, "显式回滚改变了数据")
        clone.query(sql)
        require(clone.fingerprints(list(private), private_columns) == private, "隔离库个人记录发生改变")
        again, _ = inspect(clone, source, release)
        require(not any(again.inserts.values()) and not again.updates, "重复预览不幂等")
        for table, rows in plan.inserts.items():
            require(int(clone.query("SELECT COUNT(*) FROM " + ident(table) + ";"))
                    == len(baseline.get(table, [])) + len(rows), "导入数量不一致")
        report["rehearsal"] = {"backupRestored": True, "failureRollback": True, "explicitRollback": True,
                               "personalTablesUnchanged": True, "idempotent": True,
                               "backupSha256": hashlib.sha256(backup.read_bytes()).hexdigest()}
    finally:
        if created:
            require(re.fullmatch(r"kaoyan_deploy_verify_[a-f0-9]{16}", clone_name), "隔离库边界错误")
            db.query("DROP DATABASE " + ident(clone_name) + ";", server=True)


def main() -> None:
    """Run a read-only preview, or an explicitly selected isolated rehearsal."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rehearse", action="store_true")
    parser.add_argument("--diagnose", action="store_true", help="Read-only public question/document differences")
    parser.add_argument("--socket", help="Root socket override, primarily for isolated verification")
    args = parser.parse_args()
    require(not (args.diagnose and args.rehearse), "诊断不能与预演同时使用")
    os.umask(0o077)
    require(not args.output.exists(), "输出目录已存在，请换新目录")
    config = dotenv_values(args.env_file)
    require(config.get("DB_NAME") and config.get("DB_USER"), "数据库配置缺失")
    require(not config.get("SPRING_DATASOURCE_URL"), "存在数据源URL覆盖")
    require(config.get("DB_HOST", "127.0.0.1") in ("127.0.0.1", "localhost", "::1"), "仅支持本机MySQL")
    ident(str(config["DB_NAME"]))
    environment = os.environ.copy()
    if args.rehearse:
        environment.pop("MYSQL_PWD", None)
        options = ["--protocol=SOCKET", "--user=root"]
        if args.socket:
            options.append("--socket=" + args.socket)
    else:
        environment["MYSQL_PWD"] = config.get("DB_PASSWORD") or ""
        options = ["--protocol=TCP", "--host=" + str(config.get("DB_HOST") or "127.0.0.1"),
                   "--port=" + str(config.get("DB_PORT") or "3306"), "--user=" + str(config["DB_USER"])]
    options.extend(["--default-character-set=utf8mb4"])
    db = Database(str(config["DB_NAME"]), options, environment)
    data_path = args.release_root / "public-data/public-content.json"
    source_sha = hashlib.sha256(data_path.read_bytes()).hexdigest()
    exported = json.loads(data_path.read_text())
    receipt = json.loads((data_path.parent / "EXPORT-SUMMARY.json").read_text())
    require(source_sha == receipt["sha256"] and exported["format"] == "kaoyan-public-content-v1", "资料校验失败")
    require(exported["counts"] == {name: len(rows) for name, rows in exported["tables"].items()}, "资料数量不一致")
    source = exported["tables"]
    if args.diagnose:
        require(set(source) == set(PUBLIC), "资料表白名单不符")
        reports = [diagnose_rows(table, source[table], db.public_rows(table, list(source[table][0])))
                   for table in ("question", "document")]
        report: Row = {"sourceSha256": source_sha, "diagnostics": reports, "databaseWritesPerformed": False}
        args.output.mkdir(mode=0o700, parents=True)
        (args.output / "diagnostics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    plan, pending = inspect(db, source, args.release_root)
    report = summary(plan, pending, source_sha)
    args.output.mkdir(mode=0o700, parents=True)
    (args.output / "preview.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if args.rehearse:
        rehearse(db, source, args.release_root, args.output, report)
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("生产库未执行迁移或资料写入。输出目录：", args.output)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        if isinstance(error, RuntimeError):
            raise SystemExit(str(error)) from None
        raise SystemExit("预演未完成，异常类别=" + type(error).__name__ + "；生产库未执行迁移或资料写入") from None
