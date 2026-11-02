"""Replay public school metrics on a disposable MySQL instance, never the daily DB."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

from school_metrics import database_values, load_manifest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("smoke_helpers", ROOT / "scripts/smoke-current.py")
HELPERS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPERS)
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def literal(value: object) -> str:
    """Quote fixture SQL values without shell interpolation."""
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def main() -> None:
    """Start isolated services, replay public inputs, and save a credential-free report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--browser", action="store_true", help="Check the production Vue build in isolated browser contexts")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; choose a new path")
    mysql = shutil.which("mysql") or "/opt/homebrew/opt/mysql@8.4/bin/mysql"
    mysqld = "/opt/homebrew/opt/mysql@8.4/bin/mysqld"
    classpath = ROOT / "kaoyan-B/target/test-classpath.txt"
    manifest = load_manifest(ROOT / "outputs/school-enrichment-20261101/final/manifest.json")
    artifacts = args.output.with_suffix("")
    artifacts.mkdir(parents=True, exist_ok=False)
    report = {"dailyDatabaseAccessed": False, "modelCalls": 0, "checks": []}
    processes = []
    handles = []
    with tempfile.TemporaryDirectory(prefix="school-catalog-mysql-") as directory:
        temp = Path(directory)
        ports = set()
        while len(ports) < 3:
            ports.add(HELPERS.free_port())
        db_port, java_port, agent_port = sorted(ports)
        env = {**os.environ, "MYSQL_PWD": "", "AGENT_INTERNAL_KEY": secrets.token_hex(24),
               "JWT_SECRET": secrets.token_hex(32), "LLM_ENABLED": "false", "LLM_API_KEY": "",
               "RAG_BACKEND": "lexical", "RAG_DATA": str(ROOT / "kaoyan-agent/knowledge/corpus.json"),
               "QUESTION_INDEX": str(temp / "questions"), "QUESTION_MODEL_CACHE": str(temp / "models"),
               "MINUTE_TASK_LIMIT": "30", "DAILY_TASK_LIMIT": "100",
               "AGENT_BASE_URL": f"http://127.0.0.1:{agent_port}", "ADMISSION_MCP_ENABLED": "false"}

        def start(name: str, command: list[str], cwd: Path) -> subprocess.Popen:
            """Start only a task-owned process with a separate log."""
            handle = (artifacts / f"{name}.log").open("w")
            handles.append(handle)
            process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=handle, stderr=subprocess.STDOUT)
            processes.append(process)
            return process

        def sql(statement: str) -> str:
            """Execute only against this disposable server on its random port."""
            result = subprocess.run([mysql, "--no-defaults", "--protocol=TCP", "--host=127.0.0.1",
                                     f"--port={db_port}", "--user=root", "--default-character-set=utf8mb4", "-N", "-B"],
                                    input=statement, text=True, capture_output=True, env=env, timeout=15)
            if result.returncode:
                raise RuntimeError("Isolated SQL failed; parameters withheld")
            return result.stdout.strip()

        def api(path: str, token: str = "", data: dict | None = None, method: str | None = None) -> tuple[int, dict]:
            """Call the isolated Java API without printing tokens or request bodies."""
            request = urllib.request.Request(f"http://127.0.0.1:{java_port}/api{path}",
                method=method,
                headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})},
                data=json.dumps(data).encode() if data is not None else None)
            try:
                with HTTP.open(request, timeout=20) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)

        try:
            init = subprocess.run([mysqld, "--no-defaults", "--initialize-insecure", f"--datadir={temp / 'data'}"],
                                  env=env, capture_output=True, timeout=60)
            if init.returncode:
                raise RuntimeError("Isolated MySQL initialization failed")
            database = start("mysql", [mysqld, "--no-defaults", f"--datadir={temp / 'data'}", "--bind-address=127.0.0.1",
                f"--port={db_port}", f"--socket={temp / 'mysql.sock'}", "--mysqlx=OFF", "--skip-log-bin"], temp)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if database.poll() is not None:
                    raise RuntimeError("Isolated MySQL exited")
                try:
                    if sql("SELECT 1;") == "1":
                        break
                except RuntimeError:
                    pass
                time.sleep(.2)
            else:
                raise RuntimeError("Isolated MySQL not ready")
            sql("CREATE DATABASE school_lookup_smoke CHARACTER SET utf8mb4;")
            for version in (1, 7, 8, 9, 10, 11, 12, 13, 14):
                migration = next((ROOT / "kaoyan-B/src/main/resources/db").glob(f"V{version}__*.sql"))
                sql("USE school_lookup_smoke;\n" + migration.read_text())
            for school in manifest.schools:
                sql("USE school_lookup_smoke; INSERT INTO school(id,name,level) VALUES(" + ",".join(
                    literal(value) for value in (school.school_id, school.name, school.level)) + ");")
            entries = [entry for entry in manifest.entries if entry.target.school_id == 11 or entry.target.school == "北京大学"]
            for entry in entries:
                target = entry.target
                sql("USE school_lookup_smoke; INSERT INTO school_detail(id,school_id,major_name,major_code,year,remark) VALUES(" +
                    ",".join(literal(value) for value in (target.detail_id, target.school_id, "隔离回放专业", target.major_code,
                        target.year, "公开指标清单隔离回放；不代表新增审核")) + ");")
                for kind in ("ENROLLMENT", "CUTOFF_REFERENCE"):
                    row = database_values(entry, kind)
                    sql("USE school_lookup_smoke; INSERT INTO school_admission_metric(" + ",".join(row) + ") VALUES(" +
                        ",".join(literal(value) for value in row.values()) + ");")
            agent = start("agent", [sys.executable, "-m", "uvicorn", "main:create_app", "--factory", "--host", "127.0.0.1",
                                    "--port", str(agent_port)], ROOT / "kaoyan-agent")
            HELPERS.wait_ready(agent, f"http://127.0.0.1:{agent_port}", "/health")
            cp = os.pathsep.join([str(ROOT / "kaoyan-B/target/test-classes"), str(ROOT / "kaoyan-B/target/classes"), classpath.read_text().strip()])
            java = start("java", ["java", "-cp", cp, "com.kaoyan.FrameworkSmokeServer", "--server.address=127.0.0.1",
                f"--server.port={java_port}", "--spring.datasource.driver-class-name=com.mysql.cj.jdbc.Driver",
                f"--spring.datasource.url=jdbc:mysql://127.0.0.1:{db_port}/school_lookup_smoke?serverTimezone=Asia/Shanghai&useSSL=false&allowPublicKeyRetrieval=true",
                "--spring.datasource.username=root", "--spring.datasource.password=", "--spring.sql.init.mode=never",
                "--kaoyan.learning.enabled=false"], temp)
            HELPERS.wait_ready(java, f"http://127.0.0.1:{java_port}", "/api/conversations", 401)
            account = {"username": "school_lookup_smoke", "password": "synthetic-school-password"}
            assert api("/auth/register", data=account)[0] == 200
            token = api("/auth/login", data=account)[1]["data"]["accessToken"]
            started = time.monotonic()
            status, body = api("/schools/11", token)
            report.update(detailStatus=status, detailElapsedMs=round((time.monotonic() - started) * 1000),
                          detailCode=body.get("code"), replayedMetrics=len(entries) * 2)
            if not args.baseline:
                assert status == 200 and body["data"]["school"]["name"] == "四川大学"
                assert body["data"]["details"]
                report["checks"].append("MySQL四川大学详情及公开指标回放")
                assert api("/schools/999999", token)[0] == 404
                assert api("/schools/11")[0] == 401
                bad_id = entries[0].target.detail_id
                saved = sql(f"USE school_lookup_smoke; SELECT sources_json FROM school_admission_metric WHERE school_detail_id={bad_id} AND metric_type='ENROLLMENT';")
                sql(f"USE school_lookup_smoke; UPDATE school_admission_metric SET sources_json='null' WHERE school_detail_id={bad_id} AND metric_type='ENROLLMENT';")
                partial_status, partial = api("/schools/" + str(entries[0].target.school_id), token)
                assert partial_status == 200 and partial["data"]["warnings"]
                sql(f"USE school_lookup_smoke; UPDATE school_admission_metric SET sources_json={literal(saved)} WHERE school_detail_id={bad_id} AND metric_type='ENROLLMENT';")
                report["checks"].append("MySQL无效指标局部隔离、404及未认证拒绝")
                assert api("/users/profile", token, {"examYear": 2027}, method="PUT")[0] == 200

                def chat(query: str) -> tuple[str, dict]:
                    """Create a synthetic chat and wait for its persisted terminal snapshot."""
                    conversation = api("/conversations", token, {})[1]["data"]["id"]
                    status, sent = api(f"/conversations/{conversation}/messages", token,
                                       {"query": query, "clientRequestId": secrets.token_hex(8)})
                    assert status == 200, sent
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline:
                        latest = api(f"/conversations/{conversation}/messages", token)[1]["data"]["list"][0]["attempts"][-1]
                        if latest["status"] != "RUNNING":
                            assert latest["status"] == "SUCCESS", latest.get("errorMessage")
                            return conversation, latest["result"]
                        time.sleep(.1)
                    raise RuntimeError("Isolated catalog chat did not finish")

                conversation, result = chat("帮我查询北京大学的招生信息")
                assert result["schoolCatalog"]["targetYear"] == 2027
                assert result["schoolCatalog"]["total"] > 0
                assert result["admissionLinks"]["schoolName"] == "北京大学"
                assert len(result["schoolCatalog"]["details"]) <= 10
                _, missing_year = chat("查询北京大学2028年招生信息")
                assert missing_year["schoolCatalog"]["total"] == 0
                assert missing_year["schoolCatalog"]["targetYear"] == 2028
                report["checks"].append("真实HTTP聊天：档案年份、北京大学快照及官网链接、目标年缺失不换年")
                # Prove catalog lookups do not depend on Python availability.
                agent.terminate()
                agent.wait(timeout=8)
                _, independent = chat("查询四川大学招生信息")
                assert independent["schoolCatalog"]["school"]["name"] == "四川大学"
                sql("USE school_lookup_smoke; UPDATE school_detail SET remark='changed-after-snapshot' WHERE school_id=" +
                    str(result["schoolCatalog"]["school"]["id"]) + ";")
                persisted = api(f"/conversations/{conversation}/messages", token)[1]["data"]["list"][0]["attempts"][-1]["result"]
                assert persisted["schoolCatalog"] == result["schoolCatalog"]
                report["checks"].append("Python停止后仍可查询；历史院校快照不随资料更新")
                if args.browser:
                    front_port = HELPERS.free_port()
                    env["API_PROXY_TARGET"] = f"http://127.0.0.1:{java_port}"
                    frontend = start("frontend", ["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1",
                                                  "--port", str(front_port), "--strictPort"], ROOT / "kaoyan-frontend")
                    HELPERS.wait_ready(frontend, f"http://127.0.0.1:{front_port}", "/login", 200)
                    browser = subprocess.run(["node", str(ROOT / "scripts/browser-school-catalog.cjs"),
                        f"http://127.0.0.1:{front_port}", str(artifacts.resolve()), conversation],
                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
                    if browser.returncode:
                        (artifacts / "browser-failure.log").write_text(browser.stderr)
                        raise RuntimeError("Isolated school browser check failed; see browser-failure.log")
                    report["checks"].append("真实MySQL／Java／Vue隔离Chrome桌面和移动视口")
                sql("USE school_lookup_smoke; DROP TABLE school_admission_metric;")
                assert api("/schools/11", token)[0] == 200
                report["checks"].append("真实MySQL缺V14表兼容，不自动建表")
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(json.dumps(report, ensure_ascii=False))
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            for handle in handles:
                handle.close()


if __name__ == "__main__":
    main()
