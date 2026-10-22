"""Question admin browser regression: loopback Java/H2, Redis double, no external model or business DB."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def ready(process, url, expected, body=None):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('Isolated smoke process exited; inspect its test log')
        try:
            try:
                response = HTTP.open(urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                    headers={"Content-Type": "application/json"}), timeout=2)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                if response.status == expected:
                    return
        except OSError:
            pass
        time.sleep(.2)
    raise RuntimeError('Isolated smoke process did not become ready')


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--node', default='node')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Report exists; choose a new output path')
    classpath = ROOT / 'kaoyan-B/target/test-classpath.txt'
    if not classpath.is_file() or not (ROOT / 'kaoyan-frontend/dist/index.html').is_file():
        parser.error('Build frontend and Java test classes/classpath first; see README')
    java = frontend = None
    with tempfile.TemporaryDirectory(prefix='kaoyan-question-admin-') as directory:
        temp = Path(directory)
        java_port = free_port()
        frontend_port = free_port()
        while frontend_port == java_port:
            frontend_port = free_port()
        java_base = f'http://127.0.0.1:{java_port}'
        frontend_base = f'http://127.0.0.1:{frontend_port}'
        env = {**os.environ, 'JWT_SECRET': secrets.token_hex(32), 'AGENT_INTERNAL_KEY': secrets.token_hex(32),
               'AGENT_BASE_URL': 'http://127.0.0.1:1', 'API_PROXY_TARGET': java_base,
               'NODE_PATH': str(ROOT / 'kaoyan-frontend/node_modules')}
        cp = os.pathsep.join([str(ROOT / 'kaoyan-B/target/test-classes'),
                              str(ROOT / 'kaoyan-B/target/classes'), classpath.read_text().strip()])
        with (temp / 'java.log').open('w') as java_log, (temp / 'frontend.log').open('w') as frontend_log:
            try:
                java = subprocess.Popen(['java', '-cp', cp, 'com.kaoyan.QuestionAdminSmokeServer',
                    '--server.address=127.0.0.1', f'--server.port={java_port}',
                    '--spring.datasource.driver-class-name=org.h2.Driver',
                    '--spring.datasource.url=jdbc:h2:mem:question-admin-smoke;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER',
                    '--spring.datasource.username=sa', '--spring.datasource.password=',
                    '--spring.sql.init.mode=always',
                    '--spring.sql.init.schema-locations=classpath:schema-test.sql,classpath:schema-practice.sql'],
                    cwd=temp, env=env, stdout=java_log, stderr=subprocess.STDOUT)
                ready(java, java_base + '/api/auth/login', 200,
                      {'username': 'question_admin', 'password': 'test-only-question-password'})
                frontend = subprocess.Popen([args.node, 'node_modules/vite/bin/vite.js', 'preview', '--host',
                    '127.0.0.1', '--port', str(frontend_port), '--strictPort'], cwd=ROOT / 'kaoyan-frontend',
                    env=env, stdout=frontend_log, stderr=subprocess.STDOUT)
                ready(frontend, frontend_base, 200)
                result = subprocess.run([args.node, str(ROOT / 'scripts/browser-question-admin.cjs'), frontend_base],
                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
                if result.returncode:
                    raise RuntimeError('Question browser regression failed: ' + result.stderr[-1200:])
                report = json.loads(result.stdout)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open('x') as output:
                    json.dump(report, output, ensure_ascii=False, indent=2)
                print(f'Question admin browser checks passed: {len(report["checks"])}; report: {args.output}')
            finally:
                stop(frontend)
                stop(java)


if __name__ == '__main__':
    main()
