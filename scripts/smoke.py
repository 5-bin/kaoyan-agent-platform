"""有限时长的真实三层冒烟测试；仅使用临时进程、随机端口、独立测试数据。"""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def call(base, path, method="GET", body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            text = response.read().decode()
            return response.status, json.loads(text) if text else None
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())


def ready(process, base, path):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("测试进程启动失败，请检查测试环境")
        try:
            if call(base, path)[0] == 200:
                return
        except (OSError, TimeoutError):
            pass
        time.sleep(0.2)
    raise RuntimeError("测试进程启动超时")


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser-check", action="store_true", help="在临时后端上执行真实页面检查，需要Node/Playwright")
    parser.add_argument("--node", default="node", help="Node可执行文件")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("报告已存在，请使用新的文件名")
    jar = ROOT / "backend/target/kaoyan-agent-platform-0.1.0.jar"
    if not jar.exists():
        parser.error("请先构建 Java JAR")
    checks = []
    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)
    java = python = None
    with tempfile.TemporaryDirectory(prefix="kaoyan-agent-platform-smoke-") as directory:
        temporary = Path(directory)
        python_port, java_port = free_port(), free_port()
        while java_port == python_port:
            java_port = free_port()
        python_base, java_base = f"http://127.0.0.1:{python_port}", f"http://127.0.0.1:{java_port}"
        env = {**os.environ, "AGENT_INTERNAL_KEY": secrets.token_hex(24), "AGENT_MODE": "demo", "PORT": str(java_port),
               "BIND_ADDRESS": "127.0.0.1", "DB_URL": f"jdbc:h2:file:{temporary}/database;MODE=PostgreSQL", "DB_USER": "sa", "DB_PASSWORD": "",
               "AGENT_BASE_URL": python_base, "MINUTE_TASK_LIMIT": "100", "DAILY_TASK_LIMIT": "20"}
        # 不受宿主付费模型配置、知识路径、代理或端口配置影响。
        env.pop("KNOWLEDGE_PATH", None)
        with (temporary / "python.log").open("w") as python_log, (temporary / "java.log").open("w") as java_log:
            try:
                python = subprocess.Popen([sys.executable, "-m", "uvicorn", "agent_service.api:create_app", "--factory", "--host", "127.0.0.1", "--port", str(python_port)], cwd=ROOT / "agent", env=env, stdout=python_log, stderr=subprocess.STDOUT)
                ready(python, python_base, "/health")
                def start_java():
                    process = subprocess.Popen(["java", "-jar", str(jar)], cwd=temporary, env=env, stdout=java_log, stderr=subprocess.STDOUT)
                    try:
                        ready(process, java_base, "/api/health")
                    except Exception:
                        stop(process)
                        raise
                    return process
                java = start_java()
                check("游客不可读取历史", call(java_base, "/api/tasks")[0] == 401)
                status, account = call(java_base, "/api/auth/register", "POST", {"username": "smoke_user", "password": "test-password"})
                check("注册成功", status == 200)
                token = account["token"]
                check("注册仅创建学生账号", account["user"]["role"] == "student")
                check("待开发档案明确返回501", call(java_base, "/api/profile", token=token)[0] == 501)
                check("管理权限由服务端拒绝", call(java_base, "/api/admin/documents", token=token)[0] == 403)
                check("未实现择校不会创建假结果", call(java_base, "/api/tasks", "POST",
                    {"taskType": "school_recommendation", "input": "请根据档案推荐学校"}, token)[0] == 501)
                status, task = call(java_base, "/api/tasks", "POST", {"input": "请解释进程与线程和TCP可靠传输"}, token)
                check("Java调用真实Python并返回演示结果", status == 200 and task["status"] == "completed" and task["result"]["mode"] == "demo")
                check("返回实际资料引用", len(task["result"]["sources"]) == 2)
                check("返回类型化任务和演示版本", task["taskType"] == "knowledge_qa" and task["result"]["releaseId"] == "demo-408-v1")
                status, history = call(java_base, "/api/tasks", token=token)
                check("历史记录保存", status == 200 and history["totalItems"] == 1)
                status, other = call(java_base, "/api/auth/register", "POST", {"username": "smoke_other", "password": "test-password"})
                check("其他账号无法读取任务", status == 200 and call(java_base, "/api/tasks/" + task["id"], token=other["token"])[0] == 404)
                check("空输入拒绝", call(java_base, "/api/tasks", "POST", {"input": "  "}, token)[0] == 400)
                status, unsupported = call(java_base, "/api/tasks", "POST", {"input": "如何养殖海水观赏鱼并进行繁育"}, token)
                check("未覆盖任务明确返回", status == 200 and unsupported["status"] == "unsupported")
                stop(java); java = start_java()
                status, restored = call(java_base, "/api/tasks/" + task["id"], token=token)
                check("重启后会话和结果保留", status == 200 and restored["result"]["answer"] == task["result"]["answer"])
                if args.browser_check:
                    browser_report = args.output.with_suffix(".browser.json")
                    subprocess.run([args.node, str(ROOT / "scripts/browser-check.cjs"), java_base, str(browser_report.resolve())],
                                   cwd=ROOT, env=env, check=True, timeout=150)
                stop(python)
                status, failed = call(java_base, "/api/tasks", "POST", {"input": "请解释进程与线程的概念区别"}, token)
                check("Python离线时保存失败状态", status == 200 and failed["status"] == "failed")
                call(java_base, "/api/auth/logout", "POST", token=token)
                check("退出使会话失效", call(java_base, "/api/tasks", token=token)[0] == 401)
            finally:
                stop(java); stop(python)
    report = {"scope": "本机真实Java→Python，演示模式，临时H2文件库；不是PostgreSQL或真实模型验收", "checks": checks, "temporaryProcessesStopped": True}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
    print(f"通过 {len(checks)} 项冒烟检查；本次临时进程已关闭。")


if __name__ == "__main__":
    main()
