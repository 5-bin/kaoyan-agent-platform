"""Check or explicitly activate the rehearsed Kaoyan release on its Ubuntu host.

Default mode is read-only. --activate gates the API, stops only the two project
services, takes and restores a fresh backup, applies the approved additive SQL,
then switches services and HTTPS static files. Program rollback never deletes
committed business data; verified backups remain available for manual recovery.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from email.message import Message
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import ssl
import subprocess
import sys
import tempfile
import time
from types import ModuleType
from typing import BinaryIO, Callable, Protocol, TypeAlias
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from dotenv import dotenv_values

HELPER_SHA = "36d81ca49e8d643fc3df9e3d3a6943accfb71f1a46ccaf6ca0569a3880d2c6d4"
SOURCE_SHA = "c215258d27fb9019d09151ec54f08edcfdd7cb46ffbdb0adf02a84b18002ee68"
EXPECTED_INSERTS = {"school": 111, "school_detail": 782, "question": 360,
                    "document": 20, "question_version": 59, "school_admission_metric": 1594}
OLD_ROOT = Path("/opt/kaoyan")
SERVICES = ("kaoyan-agent.service", "kaoyan-backend.service")
DROP_NAME = "99-kaoyan-release.conf"
Json: TypeAlias = None | bool | int | float | str | list["Json"] | dict[str, "Json"]
Row: TypeAlias = dict[str, Json]


class MaintenanceDatabase(Protocol):
    """Narrow database interface supplied by the separately verified data helper."""

    def query(self, sql: str, *, server: bool = False, timeout: int = 120) -> str:
        """Execute approved maintenance SQL with redacted error reporting."""
        ...

    def tables(self) -> list[str]:
        """List table names for private-record preservation checks."""
        ...

    def fingerprints(self, tables: list[str]) -> dict[str, list[str]]:
        """Hash records without exposing their values."""
        ...


class NoProbeRedirect(HTTPRedirectHandler):
    """Keep deployment probes on their initial loopback URL without redirects."""

    def redirect_request(self, req: Request, fp: BinaryIO, code: int, msg: str,
                         headers: Message, newurl: str) -> None:
        """Return the redirect status rather than following any new destination."""
        return None


def require(condition: object, message: str) -> None:
    """Stop on failed deployment preconditions without leaking runtime secrets."""
    if not condition:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    """Hash a file without executing or displaying its contents."""
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def nginx_versions(original: str, release: Path) -> tuple[str, str, str]:
    """Render API maintenance and new HTTPS root, retaining HTTP ACME webroot."""
    api = "location /api/ {"
    old = "root /opt/kaoyan/kaoyan-frontend/dist;"
    require(original.count(api) == 1 and original.count(old) == 2, "Nginx布局不同，停止自动切换")
    require("proxy_pass http://127.0.0.1:8080;" in original, "API上游与已核对配置不同")
    require(re.search(r"listen\s+443\s+ssl", original), "缺少现有HTTPS站点")
    index = original.rfind(old)
    require(index > original.index("listen 443"), "HTTPS根目录位置不符")
    new = original[:index] + "root " + str(release / "kaoyan-frontend/dist") + ";" + original[index + len(old):]
    gate = lambda text: text.replace(api, api + "\n        return 503;", 1)
    return gate(original), gate(new), new


def dropins(release: Path, caches: dict[str, Path], learning: bool, admission: bool) -> dict[str, str]:
    """Override only paths and explicitly selected free features; retain secrets."""
    agent = ("[Service]\nWorkingDirectory=" + str(release / "kaoyan-agent")
             + "\nExecStart=\nExecStart=" + str(release / ".venv/bin/python")
             + " -m uvicorn main:create_app --factory --host 127.0.0.1 --port 8001 --workers 1\n"
             + "Environment=PYTHONDONTWRITEBYTECODE=1\n")
    for key, value in caches.items():
        agent += "Environment=" + key + "=" + str(value) + "\n"
    if admission:
        agent += "Environment=ADMISSION_MCP_ENABLED=true\n"
    backend = ("[Service]\nWorkingDirectory=" + str(release / "kaoyan-B")
               + "\nExecStart=\nExecStart=/usr/bin/java -Xms128m -Xmx512m -jar "
               + str(release / "kaoyan-B/target/kaoyan-backend-1.0.0.jar")
               + " --spring.profiles.active=prod --server.address=127.0.0.1"
               + " --springdoc.api-docs.enabled=false --springdoc.swagger-ui.enabled=false"
               + " --knife4j.enable=false\n")
    if learning:
        backend += "Environment=KAOYAN_LEARNING_ENABLED=true\n"
    return {SERVICES[0]: agent, SERVICES[1]: backend}


def atomically_write(path: Path, content: bytes, mode: int) -> None:
    """Replace a known deployment-owned file atomically, keeping its intended mode."""
    handle, name = tempfile.mkstemp(prefix=".kaoyan-switch-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_switch(steps: list[tuple[str, Callable[[], None]]], rollback: Callable[[], None]) -> None:
    """Rollback program configuration after any failed maintenance/switch phase."""
    try:
        for label, action in steps:
            print(label, flush=True)
            action()
    except (Exception, KeyboardInterrupt):
        print("更新未完成，开始恢复旧程序配置。", flush=True)
        rollback()
        raise


@dataclass
class System:
    """Execute bounded local admin commands, storing raw diagnostics privately."""

    output: Path
    serial: int = 0

    def command(self, command: list[str], *, cwd: Path | None = None, timeout: int = 120) -> str:
        """Run an argument list without shell interpolation or printing credentials."""
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        if self.output.exists():
            self.serial += 1
            (self.output / ("command-" + str(self.serial) + ".log")).write_text(result.stdout + result.stderr)
        location = "诊断保存在私密输出目录" if self.output.exists() else "预检阶段，尚未停止服务或写入数据库"
        require(result.returncode == 0, "命令失败: " + Path(command[0]).name
                + "；exit=" + str(result.returncode) + "；" + location)
        return result.stdout.strip()

    def http(self, url: str) -> tuple[int, bytes]:
        """Probe loopback only; expired public TLS is handled in a later step."""
        require(url.startswith(("http://127.0.0.1:", "https://127.0.0.1/")), "只允许本机健康检查")
        context = ssl._create_unverified_context() if url.startswith("https:") else None
        opener = build_opener(NoProbeRedirect(), HTTPSHandler(context=context))
        try:
            with opener.open(url, timeout=4) as response:
                return response.status, response.read(2 * 1024 * 1024)
        except HTTPError as error:
            return error.code, error.read(8192)

    def wait_for(self, check: Callable[[], bool], message: str, seconds: int = 55) -> None:
        """Wait for startup readiness without launching retries of business tasks."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                if check():
                    return
            except (OSError, ValueError, URLError):
                pass
            time.sleep(1)
        raise RuntimeError(message)


@dataclass
class Activation:
    """Apply one validated plan with an API gate and program-only rollback."""

    release: Path
    rehearsal: Path
    helper_path: Path
    expected_plan: str
    output: Path
    learning: bool
    admission: bool
    system: System
    state: Row = field(default_factory=dict)
    written_dropins: list[str] = field(default_factory=list)
    helper: ModuleType | None = None
    site: Path = Path("/etc/nginx/sites-enabled/kaoyan")
    original: bytes = b""
    site_mode: int = 0o644
    candidates: tuple[str, str, str] = ("", "", "")
    caches: dict[str, Path] = field(default_factory=dict)
    overrides: dict[str, str] = field(default_factory=dict)
    source: dict[str, list[Row]] = field(default_factory=dict)
    db: MaintenanceDatabase | None = None
    committed_activation: Path | None = None
    current_plan_sha: str = ""

    def validate(self) -> dict[str, object]:
        """Read release integrity, service configuration and current public DB state."""
        require(self.release.parent == Path("/opt/kaoyan-releases"), "部署目录边界不符")
        require(re.fullmatch(r"kaoyan-release-[A-Za-z0-9._-]+", self.release.name), "版本目录名不符")
        require(sha(self.helper_path) == HELPER_SHA, "资料工具版本不符")
        require(not self.output.exists() and self.output.parent == Path("/root"), "输出目录必须是/root下的新目录")
        for line in (self.release / "MANIFEST.sha256").read_text().splitlines():
            expected, name = line.split("  ", 1)
            relative = Path(name)
            require(not relative.is_absolute() and ".." not in relative.parts, "归档路径不安全")
            candidate = self.release / relative
            require(not candidate.is_symlink() and sha(candidate) == expected, "部署文件校验失败: " + name)
        spec = importlib.util.spec_from_file_location("kaoyan_data_helper", self.helper_path)
        require(spec is not None and spec.loader is not None, "无法加载资料工具")
        self.helper = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.helper
        spec.loader.exec_module(self.helper)
        report = json.loads((self.rehearsal / "report.json").read_text())
        require(report["planSha256"] == self.expected_plan and report["sourceSha256"] == SOURCE_SHA, "预演计划不符")
        require(report["insertRows"] == EXPECTED_INSERTS and report["reuseRows"].get("school_detail") == 15,
                "预演数量与本次确认清单不同")
        require(all(report["rehearsal"].get(key) is True for key in
                    ("backupRestored", "failureRollback", "explicitRollback", "personalTablesUnchanged", "idempotent")),
                "预演检查未全部通过")
        require(sha(self.rehearsal / "server-before.sql") == report["rehearsal"]["backupSha256"], "预演备份校验失败")
        data = self.release / "public-data/public-content.json"
        require(sha(data) == SOURCE_SHA, "公共资料快照不符")
        self.source = json.loads(data.read_text())["tables"]
        values = dotenv_values(OLD_ROOT / ".env")
        require(values.get("DB_NAME") and not values.get("SPRING_DATASOURCE_URL"), "数据源配置不完整或存在覆盖")
        require(values.get("DB_HOST", "127.0.0.1") in ("127.0.0.1", "localhost", "::1"), "只支持本机MySQL")
        self.helper.ident(str(values["DB_NAME"]))
        require(str(values.get("LLM_ENABLED") or "false").lower() == "false", "本次范围仅部署模型关闭配置")
        for requested, key in ((self.learning, "KAOYAN_LEARNING_ENABLED"), (self.admission, "ADMISSION_MCP_ENABLED")):
            require(not requested or values.get(key) in (None, "", "true"), "服务器显式开关与启用项冲突: " + key)
        environment = os.environ.copy()
        environment.pop("MYSQL_PWD", None)
        self.db = self.helper.Database(str(values["DB_NAME"]),
                                       ["--protocol=SOCKET", "--user=root", "--default-character-set=utf8mb4"], environment)
        plan, pending = self.helper.inspect(self.db, self.source, self.release)
        current = self.helper.summary(plan, pending, SOURCE_SHA)
        self.current_plan_sha = str(current["planSha256"])
        if self.committed_activation is None:
            require(self.current_plan_sha == self.expected_plan, "当前公共数据或结构已改变，需要重新预演")
        else:
            prior = json.loads((self.committed_activation / "activation-result.json").read_text())
            require(prior.get("dataCommitConfirmed") is True and prior.get("personalRowsPreserved") is True,
                    "先前结果未证明数据已提交且个人记录保留")
            require(not pending and not any(plan.inserts.values()) and not plan.updates,
                    "当前库与已提交资料不一致，需要人工核对")
            counts = {table: int(self.db.query("SELECT COUNT(*) FROM " + self.helper.ident(table) + ";"))
                      for table in self.helper.PUBLIC}
            require(counts == {table: len(rows) for table, rows in self.source.items()}, "现有公共资料数量不一致")
        for service in SERVICES:
            require(self.system.command(["systemctl", "is-active", service]) == "active", "旧服务未运行: " + service)
            require(not self.drop_path(service).exists(), "已有同名切换配置，禁止覆盖")
            restrictions = self.system.command(["systemctl", "show", service, "--value", "-p", "RootDirectory"])
            require(not restrictions, "不支持不同根目录的服务")
        stage_env = self.release / ".env"
        require(not stage_env.exists() and not stage_env.is_symlink()
                or stage_env.is_symlink() and stage_env.resolve() == OLD_ROOT / ".env", "新版目录已有不同.env，停止覆盖")
        for key, name in (("RAG_INDEX", "rag"), ("QUESTION_INDEX", "questions"), ("QUESTION_MODEL_CACHE", "embedding")):
            value = Path(values.get(key) or str(OLD_ROOT / "kaoyan-agent/.cache" / name))
            if not value.is_absolute():
                value = OLD_ROOT / "kaoyan-agent" / value
            value = value.resolve()
            require(value.is_relative_to(OLD_ROOT) and not re.search(r"[\s%]", str(value)), "缓存路径需人工核对: " + key)
            self.caches[key] = value
        self.site = self.site.resolve(strict=True)
        self.original = self.site.read_bytes()
        self.site_mode = self.site.stat().st_mode & 0o777
        self.candidates = nginx_versions(self.original.decode(), self.release)
        self.overrides = dropins(self.release, self.caches, self.learning, self.admission)
        worker = re.search(r"(?m)^\s*user\s+([A-Za-z_][A-Za-z0-9_-]*)\s*[; ]", Path("/etc/nginx/nginx.conf").read_text())
        require(worker is not None, "需要先核对Nginx工作进程账号")
        self.system.command(["runuser", "-u", worker.group(1), "--", "/usr/bin/test", "-r",
                             str(self.release / "kaoyan-frontend/dist/index.html")])
        self.system.command(["runuser", "-u", "kaoyan", "--", "/usr/bin/test", "-r",
                             str(self.release / "kaoyan-B/target/kaoyan-backend-1.0.0.jar")])
        return {"release": str(self.release), "planSha256": self.expected_plan,
                "dataAlreadyCommitted": self.committed_activation is not None,
                "insertRows": {key: 0 for key in EXPECTED_INSERTS} if self.committed_activation else EXPECTED_INSERTS,
                "schoolRowsToUpdate": 0 if self.committed_activation else report["schoolRowsToUpdate"], "modelEnabled": False,
                "enableLearning": self.learning, "enableAdmissionLinks": self.admission,
                "rollbackPolicy": "恢复旧程序和Nginx；已提交的新增数据及新增表保留；不自动清空或恢复业务库"}

    def drop_path(self, service: str) -> Path:
        """Return the single deployment-owned systemd drop-in path."""
        require(service in SERVICES, "禁止修改其他服务")
        return Path("/etc/systemd/system") / (service + ".d") / DROP_NAME

    def nginx(self, text: str) -> None:
        """Validate before loading a new site configuration."""
        atomically_write(self.site, text.encode(), self.site_mode)
        self.system.command(["nginx", "-t"])
        self.system.command(["systemctl", "reload", "nginx"])

    def gate(self) -> None:
        """Block new API requests before stopping services or taking the new backup."""
        require(self.site.read_bytes() == self.original, "Nginx配置在检查后改变")
        self.state["siteTouched"] = True
        self.nginx(self.candidates[0])
        self.system.wait_for(lambda: self.system.http("https://127.0.0.1/api/_deployment_probe")[0] == 503,
                             "API维护开关未生效", seconds=15)

    def stop(self) -> None:
        """Stop only the two known project services after API maintenance is active."""
        self.state["servicesTouched"] = True
        self.system.command(["systemctl", "stop", SERVICES[1], SERVICES[0]])

    def data(self) -> None:
        """Freshly rehearse, apply additive schema and commit guarded public data."""
        require(self.helper is not None and self.db is not None, "缺少预检状态")
        directory = self.output / "database"
        directory.mkdir(mode=0o700)
        plan, pending = self.helper.inspect(self.db, self.source, self.release)
        report = self.helper.summary(plan, pending, SOURCE_SHA)
        require(report["planSha256"] == (self.current_plan_sha if self.committed_activation else self.expected_plan),
                "维护后计划变化，未执行写入")
        self.helper.rehearse(self.db, self.source, self.release, directory, report)
        (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        if self.committed_activation is not None:
            require(not pending and not any(plan.inserts.values()) and not plan.updates,
                    "已提交资料状态改变，未执行切换")
            self.state["dataAlreadyCommitted"] = True
            self.state["dataCommitConfirmed"] = True
            self.state["personalRowsPreserved"] = True
            self.state["publicCounts"] = {
                table: int(self.db.query("SELECT COUNT(*) FROM " + self.helper.ident(table) + ";"))
                for table in self.helper.PUBLIC
            }
            require(self.state["publicCounts"] == {table: len(rows) for table, rows in self.source.items()},
                    "现有公共资料数量不一致")
            return
        private = [name for name in self.db.tables() if name not in self.helper.PUBLIC]
        before = self.db.fingerprints(private)
        self.state["schemaStarted"] = True
        for path in pending:
            self.db.query(path.read_text())
        self.db.query((directory / "public-merge.sql").read_text())
        self.state["dataCommitConfirmed"] = True
        require(self.db.fingerprints(private) == before, "个人数据保护校验失败")
        self.state["personalRowsPreserved"] = True
        counts = {table: int(self.db.query("SELECT COUNT(*) FROM " + self.helper.ident(table) + ";"))
                  for table in self.helper.PUBLIC}
        require(counts == {table: len(rows) for table, rows in self.source.items()}, "导入后数量不符")
        self.state["publicCounts"] = counts

    def install(self) -> None:
        """Install small reversible service overrides and reuse protected credentials."""
        env = self.release / ".env"
        if not env.is_symlink():
            env.symlink_to(OLD_ROOT / ".env")
        account = pwd.getpwnam("kaoyan")
        for path in self.caches.values():
            missing: list[Path] = []
            current = path
            while not current.exists():
                require(current.is_relative_to(OLD_ROOT), "缓存目录越界")
                missing.append(current)
                current = current.parent
            for directory in reversed(missing):
                directory.mkdir(mode=0o755)
                os.chown(directory, account.pw_uid, account.pw_gid)
        for service, text in self.overrides.items():
            path = self.drop_path(service)
            path.parent.mkdir(parents=True, exist_ok=True)
            require(not path.exists(), "切换配置已被其他操作创建")
            atomically_write(path, text.encode(), 0o644)
            self.written_dropins.append(service)
            self.state["dropinsWritten"] = list(self.written_dropins)
        self.system.command(["systemctl", "daemon-reload"])

    def ready(self, *, new: bool) -> None:
        """Check process readiness without authentication mutations or model calls."""
        def agent_ready() -> bool:
            code, body = self.system.http("http://127.0.0.1:8001/health")
            value = json.loads(body)
            if code != 200 or value.get("status") != "ok":
                return False
            if new:
                require(value.get("modelEnabled") is False, "模型开关与本次范围不符")
                if self.admission and value.get("mcpTools", {}).get("admission", {}).get("state") != "READY":
                    return False
            return True
        self.system.wait_for(agent_ready, "Python服务未就绪")
        self.system.wait_for(lambda: self.system.http("http://127.0.0.1:8080/api/_deployment_probe")[0] == 401,
                             "Java服务未就绪")
        for service in SERVICES:
            require(self.system.command(["systemctl", "is-active", service]) == "active", "项目服务未运行")
            if new:
                actual = self.system.command(["systemctl", "show", service, "--value", "-p", "ExecStart"])
                require(str(self.release) in actual, "实际启动路径不是新版")

    def start(self) -> None:
        """Start new single-instance services while the API remains gated."""
        self.system.command(["systemctl", "start", SERVICES[0]])
        self.system.command(["systemctl", "start", SERVICES[1]])
        self.ready(new=True)

    def expose(self) -> None:
        """Verify the new static entry under maintenance, then reopen the API."""
        self.nginx(self.candidates[1])
        expected = hashlib.sha256((self.release / "kaoyan-frontend/dist/index.html").read_bytes()).hexdigest()
        def matches_index() -> bool:
            status, body = self.system.http("https://127.0.0.1/")
            return status == 200 and hashlib.sha256(body).hexdigest() == expected
        self.system.wait_for(matches_index, "新版前端入口不一致", seconds=15)
        self.nginx(self.candidates[2])
        self.system.wait_for(lambda: self.system.http("https://127.0.0.1/api/_deployment_probe")[0] == 401,
                             "API维护开关未解除", seconds=15)
        self.state["servicesSwitched"] = True

    def rollback(self) -> None:
        """Restore old code/configuration while retaining all committed business data."""
        if self.state.get("siteTouched"):
            self.nginx(self.candidates[0])
        if self.state.get("servicesTouched"):
            self.system.command(["systemctl", "stop", SERVICES[1], SERVICES[0]])
            for service in self.written_dropins:
                path = self.drop_path(service)
                require(path.read_text() == self.overrides[service], "切换配置已被其他操作改变，请人工恢复")
                path.unlink()
            self.system.command(["systemctl", "daemon-reload"])
            self.system.command(["systemctl", "start", SERVICES[0]])
            self.system.command(["systemctl", "start", SERVICES[1]])
            self.ready(new=False)
        if self.state.get("siteTouched"):
            self.nginx(self.original.decode())
        self.state["oldProgramRestored"] = True

    def activate(self) -> None:
        """Execute an explicitly requested maintenance window and persist its result."""
        require(os.geteuid() == 0, "正式更新需要在服务器root终端执行")
        self.output.mkdir(mode=0o700)
        (self.output / "nginx-before.conf").write_bytes(self.original)
        for service, text in self.overrides.items():
            (self.output / (service + ".new.conf")).write_text(text)
        try:
            run_switch([
                ("1/6 开启API维护状态", self.gate),
                ("2/6 停止项目Java和Python", self.stop),
                ("3/6 新备份、恢复预演及核对已提交资料" if self.committed_activation else
                 "3/6 新备份、恢复预演、迁移及公共资料合并", self.data),
                ("4/6 安装新版服务路径", self.install),
                ("5/6 启动并检查新版服务", self.start),
                ("6/6 切换前端并解除维护状态", self.expose),
            ], self.rollback)
        finally:
            (self.output / "activation-result.json").write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(self.state, ensure_ascii=False, indent=2))
        print("新版程序已切换；公网证书、模型权重和登录后的业务验收仍需后续完成。")
        print("私密备份与回退记录：", self.output)


def main() -> None:
    """Check by default; require an explicit flag and reviewed plan for activation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--rehearsal", type=Path, required=True)
    parser.add_argument("--data-helper", type=Path, default=Path("/root/prepare-server-data.py"))
    parser.add_argument("--expected-plan", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--enable-learning", action="store_true")
    parser.add_argument("--enable-admission-links", action="store_true")
    parser.add_argument("--committed-activation", type=Path,
                        help="Reuse a prior activation that already committed and verified its data")
    args = parser.parse_args()
    os.umask(0o077)
    activation = Activation(args.release_root.resolve(), args.rehearsal.resolve(), args.data_helper.resolve(),
                            args.expected_plan, args.output, args.enable_learning, args.enable_admission_links,
                            System(args.output))
    if args.committed_activation is not None:
        activation.committed_activation = args.committed_activation.resolve(strict=True)
    plan = activation.validate()
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if args.activate:
        activation.activate()
    else:
        print("只读检查通过；未执行正式更新。")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        if isinstance(error, RuntimeError):
            raise SystemExit(str(error)) from None
        raise SystemExit("更新未完成，异常类别=" + type(error).__name__ + "；请保留输出目录并发送末尾状态") from None
