"""Upgrade the verified Ubuntu deployment with V15 and exact config rollback.

Read-only by default. Activation requires a trusted manifest, fresh restore
rehearsal and explicit --activate. Never merges public data or undoes DDL.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass, field
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType
from typing import Iterator

from dotenv import dotenv_values

BASE_SHA = "2e9d73c81b370ab38dc83f206b55ba636e5b5cf6ed7792ec29051380e2028f5d"
HELPER_SHA = "bd0e9bd00ae786b1248c108b7105d65d7802f5e0e5657728eb43189b6a7d76cb"
V15_SHA = "480746af70a9864ec1fe1d14438c1445d9286dccb683074a761a12daf9d4acb5"
V15_NAME = "V15__profile_degree_type.sql"


def load_module(name: str, path: Path) -> ModuleType:
    """Import the reviewed local deployment components without invoking CLI code."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载升级组件")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Base module is bundled alongside this tool and separately pinned by the caller.
base = load_module("upgrade_activation_base", Path(__file__).with_name("activate-server-release.py"))
require = base.require


@contextmanager
def deployment_lock(path: Path) -> Iterator[None]:
    """Reject concurrent upgrades while holding the lock through rollback."""
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("已有升级进程运行") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def runtime_files(root: Path) -> set[str]:
    """Inventory immutable runtime files, excluding tests, caches and old assets."""
    result: set[str] = set()
    for name in ("kaoyan-agent", "config", "kaoyan-frontend/dist", "kaoyan-B/src/main/resources/db", "public-data"):
        for path in (root / name).rglob("*"):
            relative = path.relative_to(root)
            if any(part in {"tests", "__pycache__", ".cache", ".pytest_cache"} for part in relative.parts):
                continue
            if path.suffix in {".pyc", ".pyo"}:
                continue
            if path.is_file() or path.is_symlink():
                require(not path.is_symlink(), "运行文件不可为符号链接: " + str(relative))
                result.add(str(relative))
    result.add("kaoyan-B/target/kaoyan-backend-1.0.0.jar")
    return result


def verify_manifest(root: Path, manifest: Path, expected: str) -> None:
    """Check the trusted complete inventory, contents and path boundaries."""
    require(base.sha(manifest) == expected, "清单哈希不符")
    files = json.loads(manifest.read_text())
    require(isinstance(files, dict) and files, "清单为空")
    actual = runtime_files(root)
    require(set(files) == actual, "运行文件清单不符，缺失=" + str(sorted(set(files) - actual)) + "，额外=" + str(sorted(actual - set(files))))
    for name, digest in files.items():
        relative = Path(name)
        require(not relative.is_absolute() and ".." not in relative.parts, "清单路径非法")
        candidate = root / relative
        require(candidate.resolve().is_relative_to(root.resolve()) and not candidate.is_symlink(), "清单文件越界")
        require(base.sha(candidate) == digest, "文件校验失败: " + name)


def upgrade_nginx(original: str, current: Path, release: Path) -> tuple[str, str, str]:
    """Switch the one known HTTPS root and preserve all HTTP/certificate settings."""
    old = "root " + str(current / "kaoyan-frontend/dist") + ";"
    require(original.count(old) == 1 and original.count("location /api/ {") == 1, "Nginx布局不符")
    require("return 503;" not in original and "proxy_pass http://127.0.0.1:8080;" in original, "API配置不符")
    require(original.index(old) > original.index("listen 443 ssl"), "HTTPS根目录位置不符")
    new = original.replace(old, "root " + str(release / "kaoyan-frontend/dist") + ";", 1)
    gate = lambda text: text.replace("location /api/ {", "location /api/ {\n        return 503;", 1)
    return gate(original), gate(new), new


def replace_dropin(original: str, current: Path, release: Path, service: str) -> str:
    """Replace only known WorkingDirectory/ExecStart version paths."""
    suffix = "kaoyan-agent" if service == base.SERVICES[0] else "kaoyan-B"
    require(original.count("WorkingDirectory=" + str(current / suffix)) == 1, "服务工作目录不符")
    require(original.count(str(current)) == 2, "服务路径布局不符")
    require("ExecStart=" in original and "LLM_ENABLED" not in original, "服务启动配置不符")
    return original.replace(str(current), str(release))


def validate_v15(db: object) -> None:
    """Require the exact nullable varchar column and enforced allowed-value CHECK."""
    column = db.query("SELECT CONCAT(DATA_TYPE,':',CHARACTER_MAXIMUM_LENGTH,':',IS_NULLABLE,':',IF(COLUMN_DEFAULT IS NULL,'NULL',COLUMN_DEFAULT)) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='user' AND COLUMN_NAME='degree_type';")
    require(column == "varchar:16:YES:NULL", "V15列定义不符")
    check = db.query("SELECT cc.CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS cc JOIN information_schema.TABLE_CONSTRAINTS tc ON cc.CONSTRAINT_SCHEMA=tc.CONSTRAINT_SCHEMA AND cc.CONSTRAINT_NAME=tc.CONSTRAINT_NAME WHERE tc.TABLE_SCHEMA=DATABASE() AND tc.TABLE_NAME='user' AND tc.CONSTRAINT_NAME='ck_user_degree_type' AND tc.CONSTRAINT_TYPE='CHECK' AND tc.ENFORCED='YES';")
    normalized = re.sub(r"[\s`()]+|_utf8mb4|_utf8mb3", "", check.lower().replace("\\'", "'"))
    require(normalized == "degree_typeisnullordegree_typein'academic','professional'", "V15约束定义不符")


@dataclass
class Upgrade(base.Activation):
    """Apply a schema-only upgrade and restore exact existing config on failure."""

    current: Path = Path("/invalid")
    manifest: Path = Path("/invalid")
    expected_manifest: str = ""
    original_dropins: dict[str, bytes] = field(default_factory=dict)
    metadata: dict[str, tuple[int, int, int]] = field(default_factory=dict)

    def validate(self) -> dict[str, object]:
        """Check source, live schema, rehearsal, existing services and immutable files."""
        for path in (self.current, self.release):
            require(path.parent == Path("/opt/kaoyan-releases") and re.fullmatch(r"kaoyan-release-[A-Za-z0-9._-]+", path.name), "版本目录边界不符")
        require(self.current != self.release, "新旧版本相同")
        require(not self.output.exists() and self.output.parent == Path("/root"), "需全新私密输出目录")
        require(base.sha(Path(__file__).with_name("activate-server-release.py")) == BASE_SHA, "基础工具版本不符")
        require(base.sha(self.helper_path) == HELPER_SHA, "资料工具版本不符")
        verify_manifest(self.release, self.manifest, self.expected_manifest)
        require(base.sha(self.release / "kaoyan-B/src/main/resources/db" / V15_NAME) == V15_SHA, "V15 SQL不符")
        self.helper = load_module("upgrade_data_helper", self.helper_path)
        source_path = self.release / "public-data/public-content.json"
        require(base.sha(source_path) == base.SOURCE_SHA, "公共资料来源不符")
        self.source = json.loads(source_path.read_text())["tables"]
        values = dotenv_values(base.OLD_ROOT / ".env")
        require(values.get("DB_NAME") and not values.get("SPRING_DATASOURCE_URL") and values.get("DB_HOST", "127.0.0.1") in {"localhost", "127.0.0.1", "::1"}, "数据源边界不符")
        require(str(values.get("LLM_ENABLED") or "false").lower() == "false", "模型必须关闭")
        require((self.release / ".env").is_symlink() and (self.release / ".env").resolve() == base.OLD_ROOT / ".env", "新版凭证链接不符")
        environment = os.environ.copy()
        environment.pop("MYSQL_PWD", None)
        self.db = self.helper.Database(str(values["DB_NAME"]), ["--protocol=SOCKET", "--user=root", "--default-character-set=utf8mb4"], environment)
        report = json.loads((self.rehearsal / "report.json").read_text())
        require(report["planSha256"] == self.expected_plan and report["sourceSha256"] == base.SOURCE_SHA, "预演计划不符")
        require(all(report["rehearsal"].get(key) is True for key in ("backupRestored", "failureRollback", "explicitRollback", "personalTablesUnchanged", "idempotent")), "预演未通过")
        require(base.sha(self.rehearsal / "server-before.sql") == report["rehearsal"]["backupSha256"], "预演备份不符")
        plan, pending = self.helper.inspect(self.db, self.source, self.release)
        self.check_plan(plan, pending)
        summary = self.helper.summary(plan, pending, base.SOURCE_SHA)
        require(summary["planSha256"] == self.expected_plan, "当前数据库状态与预演不同")
        for service in base.SERVICES:
            require(self.system.command(["systemctl", "is-active", service]) == "active", "旧服务未运行")
            path = self.drop_path(service)
            require(not path.is_symlink(), "服务配置不可为符号链接")
            original = path.read_bytes()
            self.original_dropins[service] = original
            self.remember(path)
            self.overrides[service] = replace_dropin(original.decode(), self.current, self.release, service)
            actual = self.system.command(["systemctl", "show", service, "--value", "-p", "WorkingDirectory"])
            require(actual == str(self.current / ("kaoyan-agent" if service == base.SERVICES[0] else "kaoyan-B")), "实际工作目录不符")
            actual = self.system.command(["systemctl", "show", service, "--value", "-p", "ExecStart"])
            require(str(self.current) in actual, "实际启动路径不符")
            require(self.system.command(["systemctl", "show", service, "--value", "-p", "DropInPaths"]) == str(path), "存在额外服务覆盖配置")
        self.admission = "Environment=ADMISSION_MCP_ENABLED=true" in self.original_dropins[base.SERVICES[0]].decode()
        self.site = self.site.resolve(strict=True)
        self.original = self.site.read_bytes()
        self.remember(self.site)
        self.site_mode = self.metadata[str(self.site)][0]
        self.candidates = upgrade_nginx(self.original.decode(), self.current, self.release)
        for user, relative in (("www-data", "kaoyan-frontend/dist/index.html"), ("kaoyan", "kaoyan-B/target/kaoyan-backend-1.0.0.jar")):
            self.system.command(["runuser", "-u", user, "--", "test", "-r", str(self.release / relative)])
        self.ready(new=False)
        require(json.loads(self.system.http("http://127.0.0.1:8001/health")[1]).get("modelEnabled") is False, "运行模型未关闭")
        return {"current": str(self.current), "release": str(self.release), "migrations": [p.name for p in pending], "publicWrites": False, "planSha256": self.expected_plan, "manifestSha256": self.expected_manifest}

    def remember(self, path: Path) -> None:
        """Keep exact mode/owner of each deployment-owned existing config."""
        stat = path.stat()
        self.metadata[str(path)] = (stat.st_mode & 0o777, stat.st_uid, stat.st_gid)

    def restore(self, path: Path, content: bytes) -> None:
        """Restore backed-up content and metadata without deleting existing configs."""
        mode, uid, gid = self.metadata[str(path)]
        base.atomically_write(path, content, mode)
        os.chown(path, uid, gid)

    def check_plan(self, plan: object, pending: list[Path]) -> None:
        """Allow only absent V15, or a fully validated previously applied V15."""
        require(not any(plan.inserts.values()) and not plan.updates, "禁止公共资料写入")
        require([path.name for path in pending] in ([], [V15_NAME]), "存在其他待执行迁移")
        if not pending:
            validate_v15(self.db)

    def data(self) -> None:
        """Restore a fresh backup, then apply V15 and compare every original column."""
        plan, pending = self.helper.inspect(self.db, self.source, self.release)
        self.check_plan(plan, pending)
        report = self.helper.summary(plan, pending, base.SOURCE_SHA)
        require(report["planSha256"] == self.expected_plan, "维护后数据库计划变化")
        directory = self.output / "database"
        directory.mkdir(mode=0o700)
        self.helper.rehearse(self.db, self.source, self.release, directory, report)
        (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        tables = self.db.tables()
        columns = {table: self.db.columns(table) for table in tables}
        before = self.db.fingerprints(tables, columns)
        self.state["schemaStarted"] = bool(pending)
        for path in pending:
            require(base.sha(path) == V15_SHA, "迁移SQL已改变")
            self.db.query(path.read_text())
        validate_v15(self.db)
        require(self.db.tables() == tables and self.db.fingerprints(tables, columns) == before, "原有记录字段发生变化")
        if pending:
            require(self.db.query("SELECT COUNT(*) FROM `user` WHERE degree_type IS NOT NULL;") == "0", "V15新列并非全空")
        self.state.update(v15Verified=True, schemaApplied=bool(pending), originalRowsPreserved=True, publicWrites=False, backupSha256=report["rehearsal"]["backupSha256"])

    def install(self) -> None:
        """Compare preimages again and replace only reviewed version path strings."""
        verify_manifest(self.release, self.manifest, self.expected_manifest)
        for service in base.SERVICES:
            path = self.drop_path(service)
            require(path.read_bytes() == self.original_dropins[service], "服务配置在预检后改变")
        for service in base.SERVICES:
            self.written_dropins.append(service)
            self.restore(self.drop_path(service), self.overrides[service].encode())
        self.system.command(["systemctl", "daemon-reload"])

    def rollback(self) -> None:
        """Keep API gated until exact previous service configurations are healthy."""
        if self.state.get("siteTouched"):
            require(self.site.read_text() in (self.original.decode(), *self.candidates), "Nginx被并发修改，保留维护并人工处理")
            self.nginx(self.candidates[0])
        if self.state.get("servicesTouched"):
            self.system.command(["systemctl", "stop", base.SERVICES[1], base.SERVICES[0]])
            for service in self.written_dropins:
                path = self.drop_path(service)
                require(path.read_bytes() in (self.original_dropins[service], self.overrides[service].encode()), "服务配置被并发修改")
                self.restore(path, self.original_dropins[service])
            self.system.command(["systemctl", "daemon-reload"])
            self.system.command(["systemctl", "start", base.SERVICES[0]])
            self.system.command(["systemctl", "start", base.SERVICES[1]])
            self.ready(new=False)
        if self.state.get("siteTouched"):
            self.nginx(self.original.decode())
        self.state["oldProgramRestored"] = True

    def activate(self) -> None:
        """Run the authorized maintenance window and retain terminal outcome on disk."""
        require(os.geteuid() == 0, "正式升级要求root")
        self.output.mkdir(mode=0o700)
        self.state.update(status="RUNNING", current=str(self.current), release=str(self.release))
        (self.output / "nginx-before.conf").write_bytes(self.original)
        (self.output / "config-metadata.json").write_text(json.dumps(self.metadata))
        for service, content in self.original_dropins.items():
            (self.output / (service + ".before.conf")).write_bytes(content)
        try:
            base.run_switch([("开启维护", self.gate), ("停止项目服务", self.stop), ("备份恢复预演与V15", self.data), ("切换服务路径", self.install), ("新版启动检查", self.start), ("静态切换与解除维护", self.expose)], self.rollback)
            self.state["status"] = "SUCCESS"
        except BaseException:
            self.state["status"] = "FAILED"
            raise
        finally:
            (self.output / "activation-result.json").write_text(json.dumps(self.state, ensure_ascii=False, indent=2))
        print(json.dumps(self.state, ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    """Validate by default; hold the instance lock across activated validation/rollback."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("current-release", "release-root", "rehearsal", "data-helper", "manifest", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-plan", required=True)
    parser.add_argument("--expected-manifest", required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    obj = Upgrade(args.release_root.resolve(), args.rehearsal.resolve(), args.data_helper.resolve(), args.expected_plan, args.output, False, False, base.System(args.output), current=args.current_release.resolve(), manifest=args.manifest.resolve(), expected_manifest=args.expected_manifest)
    if args.activate:
        with deployment_lock(Path("/run/lock/kaoyan-upgrade.lock")):
            print(json.dumps(obj.validate(), ensure_ascii=False), flush=True)
            obj.activate()
    else:
        print(json.dumps(obj.validate(), ensure_ascii=False), flush=True)
        print("只读检查通过，未执行迁移或切换。")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error) if isinstance(error, RuntimeError) else "升级失败，异常类别=" + type(error).__name__) from None
