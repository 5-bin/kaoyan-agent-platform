"""Managed practice regression on a disposable MySQL INSTANCE, never the daily server."""
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

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('helpers', ROOT / 'scripts/smoke-current.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mysqld', default=shutil.which('mysqld') or '/opt/homebrew/opt/mysql@8.4/bin/mysqld')
    args = parser.parse_args()
    if args.output.exists(): parser.error('Report exists; choose a new output path')
    mysql = shutil.which('mysql')
    classpath = ROOT / 'kaoyan-B/target/test-classpath.txt'
    if not Path(args.mysqld).is_file() or not mysql or not classpath.exists():
        parser.error('Need local MySQL binaries and the README test classpath preparation')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='kaoyan-managed-mysql-') as directory:
        temp = Path(directory)
        temp.chmod(0o700)
        ports = set()
        while len(ports) < 3: ports.add(helpers.free_port())
        mysql_port, agent_port, java_port = sorted(ports)
        processes, logs = [], []
        env = {**os.environ, 'AGENT_INTERNAL_KEY': secrets.token_hex(32), 'JWT_SECRET': secrets.token_hex(32),
               'AGENT_BASE_URL': f'http://127.0.0.1:{agent_port}', 'LLM_API_KEY': '', 'LLM_ENABLED': 'false',
               'RAG_BACKEND': 'lexical', 'RAG_DATA': str(ROOT / 'kaoyan-agent/knowledge/corpus.json'),
               'QUESTION_INDEX': str(temp / 'question-index'), 'QUESTION_MODEL_CACHE': str(temp / 'model-cache'),
               'KAOYAN_LEARNING_ENABLED': 'true', 'MINUTE_TASK_LIMIT': '30', 'DAILY_TASK_LIMIT': '100',
               'LANGSMITH_TRACING': 'false', 'LANGCHAIN_TRACING_V2': 'false'}
        mysql_env = {**env, 'MYSQL_PWD': ''}
        mysql_options = [mysql, '--no-defaults', '--protocol=TCP', '--host=127.0.0.1', f'--port={mysql_port}',
                         '--user=root', '--default-character-set=utf8mb4', '-N', '-B']

        def sql(statement):
            result = subprocess.run(mysql_options, input=statement, env=mysql_env, capture_output=True, text=True, timeout=30)
            if result.returncode: raise RuntimeError('Isolated MySQL statement failed; SQL/parameters withheld')
            return result.stdout.strip()

        def start(name, command, cwd):
            log = (temp / (name + '.log')).open('w'); logs.append(log)
            p = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            processes.append(p)
            return p

        base = f'http://127.0.0.1:{java_port}'

        def api(endpoint, method='GET', data=None, token=None, expected=200):
            request = urllib.request.Request(base + '/api' + endpoint, method=method,
                headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + token} if token else {})},
                data=json.dumps(data).encode() if data is not None else None)
            try:
                with HTTP.open(request, timeout=15) as r: status, body = r.status, json.load(r)
            except urllib.error.HTTPError as error: status, body = error.code, json.load(error)
            if status != expected or expected == 200 and body.get('code') != 0:
                raise RuntimeError(f'Isolated HTTP {method} {endpoint.split("?")[0]} expected {expected}, received {status}')
            return body.get('data')

        def account(name):
            credentials = {'username': name, 'password': 'synthetic-mysql-password'}
            api('/auth/register', 'POST', credentials)
            return api('/auth/login', 'POST', credentials)['accessToken']

        try:
            init = subprocess.run([args.mysqld, '--no-defaults', '--initialize-insecure', f'--datadir={temp / "data"}'],
                env=env, capture_output=True, timeout=60)
            if init.returncode: raise RuntimeError('Disposable MySQL initialization failed')
            db = start('mysql', [args.mysqld, '--no-defaults', f'--datadir={temp / "data"}',
                '--bind-address=127.0.0.1', f'--port={mysql_port}', f'--socket={temp / "mysql.sock"}',
                f'--pid-file={temp / "mysql.pid"}', '--mysqlx=OFF', '--skip-log-bin'], temp)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if db.poll() is not None: raise RuntimeError('Disposable MySQL exited')
                try:
                    if sql('SELECT 1;') == '1': break
                except RuntimeError: pass
                time.sleep(.2)
            else: raise RuntimeError('Disposable MySQL not ready')
            sql('CREATE DATABASE managed_session_smoke CHARACTER SET utf8mb4;')
            migrations = [1, 7, 8, 9, 10, 11, 12, 13]
            source = ROOT / 'kaoyan-B/src/main/resources/db'
            for version in migrations:
                paths = list(source.glob(f'V{version}__*.sql'))
                if len(paths) != 1: raise RuntimeError('Ambiguous isolated schema source')
                sql('USE managed_session_smoke;\n' + paths[0].read_text())
            for i in range(5):
                sql("USE managed_session_smoke; INSERT INTO question(subject,knowledge_point,content,option_a,option_b,option_c,option_d,answer,analysis,difficulty,review_status) VALUES('数据结构','排序','隔离排序题" + str(i) + "','甲','乙','丙','丁','A','合成解析','EASY','APPROVED');")
            width = sql("SELECT character_maximum_length FROM information_schema.columns WHERE table_schema='managed_session_smoke' AND table_name='practice_record' AND column_name='session_id';")
            assert width == '36'
            agent = start('agent', [sys.executable, '-m', 'uvicorn', 'tests.chat_wire_app:app', '--host', '127.0.0.1', '--port', str(agent_port)], ROOT / 'kaoyan-agent')
            helpers.wait_ready(agent, f'http://127.0.0.1:{agent_port}', '/health')
            cp = os.pathsep.join([str(ROOT / 'kaoyan-B/target/test-classes'), str(ROOT / 'kaoyan-B/target/classes'), classpath.read_text().strip()])
            java = start('java', ['java', '-cp', cp, 'com.kaoyan.FrameworkSmokeServer', '--server.address=127.0.0.1', f'--server.port={java_port}',
                '--spring.datasource.driver-class-name=com.mysql.cj.jdbc.Driver',
                f'--spring.datasource.url=jdbc:mysql://127.0.0.1:{mysql_port}/managed_session_smoke?serverTimezone=Asia/Shanghai&useUnicode=true&characterEncoding=utf-8&useSSL=false&allowPublicKeyRetrieval=true',
                '--spring.datasource.username=root', '--spring.datasource.password=', '--spring.sql.init.mode=never',
                '--kaoyan.learning.enabled=true', '--kaoyan.learning.initial-delay-ms=3600000'], temp)
            helpers.wait_ready(java, base, '/api/conversations', 401)
            token = account('isolated_mysql_student'); other = account('isolated_mysql_other')
            normal = api('/practice/sessions', 'POST', {'count': 1, 'questionIds': [1]}, token)['sessionId']
            diagnostic = api('/diagnostics/sessions', 'POST', token=token)['sessionId']
            for session in [normal, diagnostic]:
                assert session.startswith('L-') and len(session) <= 36
                assert api(f'/practice/sessions/{session}/state', token=token)['state'] == 'RUNNING'
            conversation = api('/conversations', 'POST', token=token)['id']
            api(f'/conversations/{conversation}/messages', 'POST', {'query': '给我出几道有关排序的题', 'clientRequestId': 'sorting-mysql'}, token)
            retried = False; deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                message = api(f'/conversations/{conversation}/messages', token=token)['list'][0]
                attempt = message['attempts'][-1]
                if attempt['status'] == 'RUNNING': time.sleep(.15); continue
                assert attempt['status'] == 'SUCCESS'
                status = attempt['result'].get('retrievalStatus')
                if status in {'BUILDING', 'BUSY'}:
                    # A single retry after bounded index startup, no production-data context.
                    if retried: raise RuntimeError('Index still unavailable after retry')
                    time.sleep(1); retried = True
                    api(f'/conversations/{conversation}/messages/{message["id"]}/retry', 'POST', {'clientRequestId': 'sorting-mysql-ready'}, token)
                    continue
                action = attempt['result']['actions'][0]; break
            else: raise RuntimeError('Isolated generation did not finish')
            assert action['count'] == 5 and action['status'] == 'PENDING'
            assert api('/practice/sessions/page?pageNum=1&pageSize=50', token=token)['total'] == 2
            endpoint = f'/conversations/{conversation}/actions/{action["id"]}/confirm'
            confirmed = api(endpoint, 'POST', token=token)
            session = confirmed['result']['sessionId']; assert len(session) <= 36 and session.startswith('L-')
            assert confirmed == api(endpoint, 'POST', token=token)
            state = api(f'/practice/sessions/{session}/state', token=token)
            assert len(state['items']) == 5 and all(item.get('answer') is None for item in state['items'])
            assert api('/practice/sessions/page?pageNum=1&pageSize=50', token=token)['total'] == 3
            first = state['items'][0]
            answer = api(f'/practice/sessions/{session}/answer', 'POST', {'questionId': first['questionId'], 'itemId': first['itemId'], 'answer': 'A', 'clientRequestId': 'mysql-first-answer'}, token)
            assert answer['isCorrect'] == 1
            api(endpoint, 'POST', token=other, expected=404)
            api(f'/practice/sessions/{session}/state', token=other, expected=404)
            report = {'environment': 'disposable independent MySQL instance, real Java/Python, Redis/provider/vector doubles',
                'dailyDatabaseAccessed': False, 'practiceRecordSessionColumnWidth': 36,
                'normalSessionLength': len(normal), 'diagnosticSessionLength': len(diagnostic), 'assistantSessionLength': len(session),
                'checks': ['normal_practice', 'diagnostic', 'assistant_original_request', 'preview_creates_no_session',
                           'confirmation_creates_five_items', 'repeat_confirmation_reuses_session', 'unanswered_answers_hidden',
                           'server_grading', 'cross_account_confirmation_denied', 'cross_account_state_denied']}
            with args.output.open('x') as f: json.dump(report, f, ensure_ascii=False, indent=2)
            print(json.dumps({'report': str(args.output), 'checks': len(report['checks'])}))
        except Exception:
            debug = Path(tempfile.mkdtemp(prefix=args.output.stem + '-debug-', dir=args.output.parent)); debug.chmod(0o700)
            for log in logs: log.flush()
            for name in ['mysql', 'agent', 'java']:
                if (temp / (name + '.log')).exists(): shutil.copyfile(temp / (name + '.log'), debug / (name + '.log'))
            print('Private isolated diagnostics: ' + str(debug), file=sys.stderr)
            raise
        finally:
            for process in reversed(processes): helpers.stop(process)
            for log in logs: log.close()


if __name__ == '__main__': main()
