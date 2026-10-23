"""新框架HTTP链路检查：随机端口、H2、Redis/模型替身，清理本次子进程。"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCAL_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def call(base, path, method='GET', body=None, token=''):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers=headers, method=method)
    try:
        response = LOCAL_HTTP.open(request, timeout=60)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        content = response.read().decode()
        return response.code, json.loads(content) if content else None


def wait_ready(process, base, path, expected=200):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('隔离测试服务启动失败，检查测试日志')
        try:
            try:
                response = LOCAL_HTTP.open(base + path, timeout=3)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status = response.code
            if status == expected:
                return
        except (OSError, TimeoutError):
            pass
        time.sleep(0.2)
    raise RuntimeError('隔离测试服务启动超时')


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--browser-check', action='store_true')
    parser.add_argument('--node', default='node')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('报告已存在，使用新的文件名')
    if args.browser_check and not (ROOT / 'kaoyan-frontend/dist/index.html').is_file():
        parser.error('浏览器检查需要构建产物；先在kaoyan-frontend执行 npm ci 和 npm run build')
    classpath_file = ROOT / 'kaoyan-B/target/test-classpath.txt'
    if not classpath_file.is_file():
        parser.error('先在kaoyan-B执行 ./mvnw test-compile dependency:build-classpath -Dmdep.includeScope=test -Dmdep.outputFile=target/test-classpath.txt')
    classpath = os.pathsep.join([str(ROOT / 'kaoyan-B/target/test-classes'), str(ROOT / 'kaoyan-B/target/classes'),
                                 classpath_file.read_text().strip()])
    checks = []
    def check(name, condition):
        checks.append({'name': name, 'passed': bool(condition)})
        if not condition:
            raise AssertionError(name)
    python = java = frontend = None
    with tempfile.TemporaryDirectory(prefix='kaoyan-framework-smoke-') as directory:
        temporary = Path(directory)
        ports = set()
        while len(ports) < 3:
            ports.add(free_port())
        python_port, java_port, frontend_port = ports
        python_base = f'http://127.0.0.1:{python_port}'
        java_base = f'http://127.0.0.1:{java_port}'
        frontend_base = f'http://127.0.0.1:{frontend_port}'
        env = {**os.environ, 'AGENT_INTERNAL_KEY': secrets.token_hex(32), 'JWT_SECRET': secrets.token_hex(32),
               'AGENT_BASE_URL': python_base, 'LLM_API_KEY': '', 'DB_PASSWORD': '',
               'LLM_ENABLED': 'false', 'RAG_BACKEND': 'lexical',
               'NODE_PATH': str(ROOT / 'kaoyan-frontend/node_modules'),
               'DAILY_TASK_LIMIT': '100', 'MINUTE_TASK_LIMIT': '100'}
        log_handles = [(temporary / name).open('w') for name in ['python.log', 'java.log', 'frontend.log']]
        browser_diagnostics = temporary / 'browser'
        try:
            python = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'tests.wire_app:app', '--host', '127.0.0.1',
                                       '--port', str(python_port)], cwd=ROOT / 'kaoyan-agent', env=env,
                                      stdout=log_handles[0], stderr=subprocess.STDOUT)
            wait_ready(python, python_base, '/health')
            java_command = ['java', '-cp', classpath, 'com.kaoyan.FrameworkSmokeServer',
                '--server.address=127.0.0.1', f'--server.port={java_port}',
                '--spring.datasource.driver-class-name=org.h2.Driver',
                f'--spring.datasource.url=jdbc:h2:file:{temporary}/smoke;MODE=MySQL;NON_KEYWORDS=USER;WRITE_DELAY=0',
                '--spring.datasource.username=sa', '--spring.datasource.password=',
                '--spring.sql.init.mode=always', '--spring.sql.init.schema-locations=classpath:schema-test.sql']
            java = subprocess.Popen(java_command, cwd=temporary, env=env,
                                    stdout=log_handles[1], stderr=subprocess.STDOUT)
            wait_ready(java, java_base, '/api/tasks', 401)
            check('游客任务接口401', call(java_base, '/api/tasks')[0] == 401)
            for name in ['smoke_alpha', 'smoke_beta']:
                check('注册' + name, call(java_base, '/api/auth/register', 'POST',
                    {'username': name, 'password': 'test-password'})[0] == 200)
            tokens = []
            for name in ['smoke_alpha', 'smoke_beta']:
                status, result = call(java_base, '/api/auth/login', 'POST', {'username': name, 'password': 'test-password'})
                check('登录' + name, status == 200)
                tokens.append(result['data']['accessToken'])
            token, other = tokens
            status, task = call(java_base, '/api/tasks', 'POST', {'taskType': 'KNOWLEDGE_QA', 'input': {'query': '解释进程'}}, token)
            check('真实Java→Python调用及结果保存', status == 200 and task['data']['status'] == 'SUCCESS')
            task_id = task['data']['id']
            check('跨账号任务404', call(java_base, '/api/tasks/' + task_id, token=other)[0] == 404)
            check('批次不存在时不创建总结任务', call(java_base, '/api/practice/sessions/foreign/ai-summary', 'POST', token=token)[0] == 404)
            for _ in range(24):
                status, result = call(java_base, '/api/tasks', 'POST', {'taskType': 'KNOWLEDGE_QA', 'input': {'query': 'HTTP测试'}}, token)
                if status != 200 or result['data']['status'] != 'SUCCESS':
                    raise AssertionError('生成隔离分页数据失败')
            status, history = call(java_base, '/api/tasks?pageNum=2&pageSize=20', token=token)
            check('第二页及总数正确', status == 200 and history['data']['total'] == 25 and len(history['data']['list']) == 5)
            if args.browser_check:
                frontend_env = {**env, 'API_PROXY_TARGET': java_base}
                frontend = subprocess.Popen([args.node, 'node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1',
                    '--port', str(frontend_port), '--strictPort'], cwd=ROOT / 'kaoyan-frontend', env=frontend_env,
                    stdout=log_handles[2], stderr=subprocess.STDOUT)
                wait_ready(frontend, frontend_base, '/')
                subprocess.run([args.node, str(ROOT / 'scripts/browser-current.cjs'), frontend_base, str(browser_diagnostics)],
                               cwd=ROOT, env=env, check=True, timeout=120)
                check('实际后端任务页面与账号隔离检查', True)
            def interrupted_call():
                try:
                    call(java_base, '/api/tasks', 'POST',
                         {'taskType': 'KNOWLEDGE_QA', 'input': {'query': 'simulate-interruption'}}, token)
                except (OSError, TimeoutError):
                    pass
            pending = threading.Thread(target=interrupted_call, daemon=True)
            pending.start()
            interrupted = None
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                _, recent = call(java_base, '/api/tasks', token=token)
                # This isolated fixture has one pending request; public task
                # views intentionally omit private inputPayload.
                interrupted = next((item for item in recent['data']['list']
                    if item['taskType'] == 'KNOWLEDGE_QA' and item['status'] == 'RUNNING'), None)
                if interrupted:
                    break
                time.sleep(0.1)
            check('模型调用期间RUNNING已落库', interrupted is not None)
            stop(java)
            pending.join(timeout=3)
            java = subprocess.Popen(java_command, cwd=temporary, env=env,
                                    stdout=log_handles[1], stderr=subprocess.STDOUT)
            wait_ready(java, java_base, '/api/tasks', 401)
            # Tomcat can serve requests before ApplicationRunner completes task recovery.
            deadline = time.monotonic() + 10
            while True:
                status, recovered = call(java_base, '/api/tasks/' + interrupted['id'], token=token)
                if status == 200 and recovered['data']['status'] == 'FAILED':
                    break
                if time.monotonic() >= deadline:
                    raise AssertionError('重启任务未恢复：HTTP=' + str(status) + ', status=' + str((recovered.get('data') or {}).get('status')))
                time.sleep(0.1)
            check('真实重启保留账号并恢复中断任务为FAILED', status == 200 and recovered['data']['status'] == 'FAILED'
                  and '服务重启' in recovered['data']['errorMessage'])
            stop(python)
            status, failed = call(java_base, '/api/tasks', 'POST', {'taskType': 'KNOWLEDGE_QA', 'input': {'query': '离线测试'}}, token)
            check('Python离线时保存FAILED', status == 200 and failed['data']['status'] == 'FAILED')
            check('退出接口成功', call(java_base, '/api/auth/logout', 'POST', token=token)[0] == 200)
            check('退出后令牌401', call(java_base, '/api/tasks', token=token)[0] == 401)
        except Exception:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            for handle in log_handles:
                handle.flush()
            debug = ROOT / '.cache' / ('smoke-debug-' + str(time.time_ns()))
            debug.mkdir(parents=True)
            for name in ('python.log', 'java.log', 'frontend.log'):
                shutil.copyfile(temporary / name, debug / name)
            if browser_diagnostics.is_dir():
                shutil.copytree(browser_diagnostics, debug / 'browser')
            print('测试失败，隔离服务日志保存在:', debug, file=sys.stderr)
            raise
        finally:
            stop(frontend)
            stop(java)
            stop(python)
            for handle in log_handles:
                handle.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as target:
        json.dump({'scope': '真实HTTP Java→Python；H2和Redis/模型替身；不代表MySQL/Redis/供应商验收',
                   'checks': checks, 'temporaryProcessesStopped': True}, target, ensure_ascii=False, indent=2)
    print(f'通过{len(checks)}项新框架链路检查；临时服务已停止。')


if __name__ == '__main__':
    main()
