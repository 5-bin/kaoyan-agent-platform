"""Isolated learning-loop HTTP/browser smoke: H2, real Java/Python, model off, Redis double."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import shutil
import subprocess
import tempfile
import time
import urllib.request
from importlib.util import spec_from_file_location, module_from_spec

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location("smoke_helpers", ROOT / "scripts/smoke-question-admin.py")
helpers = module_from_spec(spec)
spec.loader.exec_module(helpers)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Report exists; choose a new path")
    classpath = ROOT / "kaoyan-B/target/test-classpath.txt"
    if not classpath.is_file() or not (ROOT / "kaoyan-frontend/dist/index.html").is_file():
        parser.error("Build frontend and Java test classpath first")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    processes = []
    with tempfile.TemporaryDirectory(prefix="kaoyan-learning-loop-") as directory:
        temp = Path(directory)
        ports = set()
        while len(ports) < 3:
            ports.add(helpers.free_port())
        agent_port, java_port, frontend_port = sorted(ports)
        agent_base, java_base, front_base = [f"http://127.0.0.1:{p}" for p in (agent_port, java_port, frontend_port)]
        env = {**os.environ, "JWT_SECRET": secrets.token_hex(32), "AGENT_INTERNAL_KEY": secrets.token_hex(32),
               "AGENT_BASE_URL": agent_base, "API_PROXY_TARGET": java_base, "LLM_ENABLED": "false", "LLM_API_KEY": "",
               "RAG_BACKEND": "lexical", "RAG_INDEX": str(temp / "rag-index"),
               "QUESTION_INDEX": str(temp / "question-index"), "QUESTION_MODEL_CACHE": str(temp / "model-cache"),
               "QDRANT_URL": "", "QDRANT_API_KEY": "", "LLM_BASE_URL": "https://example.invalid/v1", "RAG_DATA": str(ROOT / "kaoyan-agent/knowledge/corpus.json"),
               "NODE_PATH": str(ROOT / "kaoyan-frontend/node_modules"), "PYTHONDONTWRITEBYTECODE": "1"}
        cp = os.pathsep.join([str(ROOT / "kaoyan-B/target/test-classes"), str(ROOT / "kaoyan-B/target/classes"), classpath.read_text().strip()])
        logs = []
        try:
            agent_log = (temp / "agent.log").open("w"); logs.append(agent_log)
            import sys
            agent = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(agent_port)], cwd=ROOT / "kaoyan-agent", env=env, stdout=agent_log, stderr=subprocess.STDOUT)
            processes.append(agent); helpers.ready(agent, agent_base + "/health", 200)
            java_log = (temp / "java.log").open("w"); logs.append(java_log)
            def start_java(first=False, worker_delay=1000):
                process = subprocess.Popen(["java", "-cp", cp, "com.kaoyan.LearningSmokeServer", "--server.address=127.0.0.1", f"--server.port={java_port}",
                    "--spring.datasource.driver-class-name=org.h2.Driver",
                    f"--spring.datasource.url=jdbc:h2:file:{temp / 'learning-smoke'};MODE=MySQL;DB_CLOSE_ON_EXIT=FALSE;WRITE_DELAY=0;NON_KEYWORDS=USER,YEAR",
                    "--spring.datasource.username=sa", "--spring.datasource.password=", f"--spring.sql.init.mode={'always' if first else 'never'}",
                    "--spring.sql.init.schema-locations=classpath:schema-test.sql,classpath:schema-practice.sql,classpath:schema-school-test.sql,classpath:schema-learning-test.sql",
                    "--kaoyan.learning.enabled=true", "--kaoyan.learning.poll-ms=1000", "--kaoyan.learning.recommend-poll-ms=1000",
                    f"--kaoyan.learning.initial-delay-ms={worker_delay}"], cwd=temp, env=env, stdout=java_log, stderr=subprocess.STDOUT)
                processes.append(process)
                helpers.ready(process, java_base + "/api/auth/login", 200, {"username": "learning_student_1", "password": "test-only-learning-password"})
                return process
            java = start_java(first=True)
            front_log = (temp / "frontend.log").open("w"); logs.append(front_log)
            front = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"], cwd=ROOT / "kaoyan-frontend", env=env, stdout=front_log, stderr=subprocess.STDOUT)
            processes.append(front); helpers.ready(front, front_base, 200)
            browser = subprocess.Popen(["node", str(ROOT / "scripts/browser-learning-loop.cjs"), front_base, str(args.output.resolve().with_suffix(""))], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            try:
                browser_out, browser_err = browser.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                os.killpg(browser.pid, signal.SIGTERM)
                try: browser_out, browser_err = browser.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(browser.pid, signal.SIGKILL)
                    browser_out, browser_err = browser.communicate(timeout=5)
                raise RuntimeError("Isolated browser timed out: " + browser_err[-2000:])
            if browser.returncode:
                raise RuntimeError("Isolated browser failed: " + browser_err[-2000:])
            report = json.loads(browser_out)
            # Restart once with workers paused, commit evidence, then abruptly stop only this Java process.
            helpers.stop(java)
            java = start_java(worker_delay=3600000)
            def api(path, method="GET", data=None, token=None):
                headers = {"Content-Type": "application/json"}
                if token: headers["Authorization"] = "Bearer " + token
                request = urllib.request.Request(java_base + "/api" + path, method=method, headers=headers,
                    data=json.dumps(data).encode() if data is not None else None)
                with helpers.HTTP.open(request, timeout=10) as response:
                    payload = json.load(response)
                    if payload["code"] != 0: raise RuntimeError("Isolated HTTP business response failed")
                    return payload["data"]
            credentials = {"username": "learning_restart", "password": "test-only-learning-password"}
            api("/auth/register", "POST", credentials)
            token = api("/auth/login", "POST", credentials)["accessToken"]
            session = api("/practice/sessions", "POST", {"subject": "数据结构", "count": 1}, token)["sessionId"]
            item = api(f"/practice/sessions/{session}/state", token=token)["items"][0]
            api(f"/practice/sessions/{session}/answer", "POST", {"questionId": item["questionId"], "itemId": item["itemId"], "answer": "B", "clientRequestId": "restart-evidence"}, token)
            if api("/learning/profile", token=token)["independentSamples"] != 0: raise RuntimeError("Workers were not paused")
            if not api(f"/practice/sessions/{session}/result", token=token)["profilePending"]: raise RuntimeError("Committed event missing")
            java.kill(); java.wait(timeout=10)
            java = start_java()
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline and api("/learning/profile", token=token)["independentSamples"] != 1:
                time.sleep(.25)
            profile = api("/learning/profile", token=token)
            if profile["independentSamples"] != 1: raise RuntimeError("Pending evidence did not recover after restart")
            if api("/stats/overview", token=token)["totalQuestions"] != 1: raise RuntimeError("Restart changed submitted statistics")
            again = api(f"/practice/sessions/{session}/answer", "POST", {"questionId": item["questionId"], "itemId": item["itemId"], "answer": "B", "clientRequestId": "restart-evidence"}, token)
            if again["isCorrect"] != 1: raise RuntimeError("Request replay did not survive restart")
            report["restartRecovery"] = {"committedEvidenceRecovered": True, "requestReplayPreserved": True, "statisticsCount": 1}
            report.update(environment="isolated temporary file H2, Redis double, real Java/Python, LLM disabled", persistentBusinessDataAccessed=False)
            with args.output.open("x") as out:
                json.dump(report, out, ensure_ascii=False, indent=2)
            print(json.dumps({"report": str(args.output), "checks": report["checks"]}, ensure_ascii=False))
        except Exception:
            debug = Path(tempfile.mkdtemp(prefix=args.output.stem + "-debug-", dir=args.output.parent))
            for log in logs: log.flush()
            for name in ("java.log", "agent.log", "frontend.log"):
                if (temp / name).exists(): shutil.copyfile(temp / name, debug / name)
            raise
        finally:
            for process in reversed(processes): helpers.stop(process)
            for log in logs: log.close()


if __name__ == "__main__":
    main()
