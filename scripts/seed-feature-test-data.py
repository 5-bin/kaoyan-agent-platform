"""Seed synthetic feature histories into dedicated STUDENT accounts; preview by default."""
import argparse
from collections import defaultdict
from datetime import datetime
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import uuid

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'scripts/fixtures/feature-test-data.json'
PRIVATE = ROOT / '.cache/feature-test-20261023'
CREDENTIALS = PRIVATE / 'credentials.json'
FEATURE_TABLES = ('practice_record', 'user_question_mark', 'study_stat', 'task',
                  'personal_document', 'personal_document_version')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sql(value):
    if value is None:
        return 'NULL'
    if isinstance(value, int):
        return str(value)
    return 'CONVERT(0x' + str(value).encode('utf-8').hex() + ' USING utf8mb4)'


def stable_id(code):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'kaoyan-feature-test-v1-20261023/' + code))


def private_json(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as target:
        json.dump(data, target, ensure_ascii=False, indent=2)


class Database:
    def __init__(self):
        values = dotenv_values(ROOT / '.env')
        host = values.get('DB_HOST') or '127.0.0.1'
        require(host in ('localhost', '127.0.0.1', '::1'), '仅允许本机数据库')
        self.env = os.environ.copy()
        self.env['MYSQL_PWD'] = values.get('DB_PASSWORD') or ''
        self.options = ['--protocol=TCP', '--default-character-set=utf8mb4', '-h', host,
                        '-P', values.get('DB_PORT') or '3306', '-u', values.get('DB_USER') or '']
        self.name = values.get('DB_NAME') or 'kaoyan'
        require(shutil.which('mysql') and shutil.which('mysqldump'), '缺少本机mysql备份工具')

    def query(self, statement):
        result = subprocess.run(['mysql', *self.options, '--connect-timeout=5', '-N', '-B', '--raw', self.name],
                                input=statement, env=self.env, text=True, encoding='utf-8',
                                capture_output=True, timeout=60)
        require(result.returncode == 0, '数据库执行失败；隐藏原始连接信息，未提交事务随连接关闭回滚')
        return result.stdout.strip()

    def rows(self, statement):
        return [json.loads(line) for line in self.query(statement).splitlines() if line]

    def backup(self, output):
        path = output / 'before.sql'
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as target:
            result = subprocess.run(['mysqldump', *self.options, '--single-transaction', '--no-tablespaces',
                                     '--set-gtid-purged=OFF', '--column-statistics=0', self.name],
                                    env=self.env, stdout=target, stderr=subprocess.PIPE, timeout=60)
        require(result.returncode == 0 and path.stat().st_size > 0, '备份失败，尚未写入测试账号及数据')
        return path


def derive(fixture, questions):
    records, stats, wrong = [], defaultdict(lambda: [0, 0, 0]), defaultdict(list)
    for session in fixture['sessions']:
        require(len(session['id']) <= 36, '批次编号过长')
        for order, attempt in enumerate(session['attempts']):
            question = questions[attempt['code']]
            selected = attempt['user_answer']
            require(selected is None or selected in 'ABCD', '作答选项不合法')
            require(bool(selected) == bool(attempt['answered_at']), '作答与时间不一致')
            correct = int(selected == question['answer']) if selected else None
            records.append(dict(session_id=session['id'], code=attempt['code'], order_index=order,
                                user_answer=selected, is_correct=correct, answered_at=attempt['answered_at'],
                                created_at=session['created_at']))
            if selected:
                counts = stats[attempt['answered_at'][:10]]
                counts[0] += 1
                counts[1] += correct
                if not correct:
                    wrong[attempt['code']].append(attempt['answered_at'])
    for day, minutes in zip(sorted(stats), fixture['study_minutes'], strict=True):
        stats[day][2] = minutes
    return records, dict(stats), dict(wrong)


def insertion(fixture, questions, owner):
    records, stats, wrong = derive(fixture, questions)
    lines = ["SET NAMES utf8mb4;", "SELECT GET_LOCK('kaoyan_feature_test_v1',10) INTO @fixture_lock;", 'START TRANSACTION;']

    def insert(table, values, condition):
        lines.append(f'INSERT INTO `{table}` (' + ','.join('`'+k+'`' for k in values) + ') SELECT ' +
                     ','.join(sql(v) for v in values.values()) + ' WHERE @fixture_lock=1 AND NOT EXISTS '
                     f'(SELECT 1 FROM `{table}` WHERE {condition});')

    for record in records:
        q = questions[record['code']]
        snapshot = None
        if record['user_answer']:
            snapshot = json.dumps(dict(id=q['id'], version=q['version'], subject=q['subject'],
                knowledgePoint=q['knowledge_point'], content=q['content'], answer=q['answer'], analysis=q['analysis'],
                optionA=q['options'][0], optionB=q['options'][1], optionC=q['options'][2], optionD=q['options'][3],
                difficulty=q['difficulty'], fixture=fixture['batch']), ensure_ascii=False)
        values = dict(user_id=owner, session_id=record['session_id'], question_id=q['id'],
                      order_index=record['order_index'], user_answer=record['user_answer'],
                      is_correct=record['is_correct'], grading_status='valid', question_snapshot=snapshot,
                      answered_at=record['answered_at'], created_at=record['created_at'])
        insert('practice_record', values, f'session_id={sql(record["session_id"])} AND question_id={q["id"]}')
    favorites = set(fixture['favorite_codes'])
    for code in sorted(set(wrong) | favorites):
        q = questions[code]
        times = wrong.get(code, [])
        insert('user_question_mark', dict(user_id=owner, question_id=q['id'], is_favorite=int(code in favorites),
               is_wrong=int(bool(times)), wrong_count=len(times), last_wrong_at=max(times) if times else None),
               f'user_id={owner} AND question_id={q["id"]}')
    for day, (count, correct, minutes) in stats.items():
        insert('study_stat', dict(user_id=owner, stat_date=day, question_count=count,
                                 correct_count=correct, study_minutes=minutes),
               f'user_id={owner} AND stat_date={sql(day)}')
    for doc in fixture['documents']:
        doc_id = stable_id('document/' + doc['code'])
        latest = len(doc['versions'])
        insert('personal_document', dict(id=doc_id, user_id=owner, title=doc['title'],
               content=doc['versions'][-1], version=latest), f'id={sql(doc_id)}')
        for version, content in enumerate(doc['versions'], 1):
            insert('personal_document_version', dict(document_id=doc_id, version=version, user_id=owner,
                   title=doc['title'], content=content, source_task_id=None),
                   f'document_id={sql(doc_id)} AND version={version}')
    for task in fixture['tasks']:
        task_id = stable_id('task/' + task['code'])
        result = None
        if task['status'] == 'SUCCESS':
            result = json.dumps(dict(outcome='NEEDS_INPUT', explanationMode='rules', resolvedTaskType='KNOWLEDGE_QA',
                answer=task['answer'], references=[], releaseId=fixture['batch'],
                notice='合成任务历史，不是实际模型调用或检索结果。'), ensure_ascii=False)
        insert('task', dict(id=task_id, user_id=owner, task_type='KNOWLEDGE_QA', status=task['status'],
               input_payload=json.dumps(dict(query=task['query'], fixture=fixture['batch']), ensure_ascii=False),
               result_payload=result, release_id=fixture['batch'], error_message=task.get('error')),
               f'id={sql(task_id)}')
    lines += ['SELECT @fixture_lock;', 'COMMIT;', "DO RELEASE_LOCK('kaoyan_feature_test_v1');"]
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    fixture = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    original = json.loads((ROOT / 'scripts/fixtures/local-test-data.json').read_text(encoding='utf-8'))
    questions = {q['code']: q.copy() for q in original['questions']}
    records, stats, wrong = derive(fixture, questions)
    expected = dict(practice_record=len(records), user_question_mark=len(set(wrong) | set(fixture['favorite_codes'])),
                    study_stat=len(stats), task=len(fixture['tasks']), personal_document=len(fixture['documents']),
                    personal_document_version=sum(len(d['versions']) for d in fixture['documents']))
    print('合成夹具预览：' + json.dumps(expected, ensure_ascii=False), flush=True)
    if not args.apply:
        print('未连接数据库；使用 --apply 才会备份、注册独立学生测试账号并插入数据。')
        return
    db = Database()
    engines = dict(line.split('\t') for line in db.query(
        'SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE();').splitlines())
    require(all(engines.get(t) == 'InnoDB' for t in ('user', 'question', *FEATURE_TABLES)), '缺少必要表，未写入；本脚本不执行迁移')
    stored_questions = db.rows("SELECT JSON_OBJECT('id',id,'version',version,'subject',subject,"
        "'knowledge_point',knowledge_point,'content',content,'answer',answer,'analysis',analysis,"
        "'difficulty',difficulty,'options',JSON_ARRAY(option_a,option_b,option_c,option_d),'locator',source_locator) "
        "FROM question WHERE source_name='local-test-data-v1-20261022';")
    require(len(stored_questions) == len(questions), '缺少首批自编题，请先核对原始夹具')
    for stored in stored_questions:
        code = stored.pop('locator').rsplit('/', 1)[-1]
        require(code in questions, '题目来源不属于已知夹具')
        require(all(stored[key] == questions[code][key] for key in
                    ('subject', 'knowledge_point', 'content', 'answer', 'analysis', 'difficulty', 'options')),
                '题目已被人工修改，停止导入以避免冒充原始快照')
        questions[code] = {**questions[code], **stored}
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    output = PRIVATE / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(mode=0o700)
    backup = db.backup(output)
    print('私密数据库备份完成。', flush=True)
    if CREDENTIALS.exists():
        credentials = json.loads(CREDENTIALS.read_text(encoding='utf-8'))
    else:
        for name in (fixture['demo_username'], fixture['empty_username']):
            require(db.query('SELECT COUNT(*) FROM user WHERE username='+sql(name)+';') == '0',
                    '测试名称已被占用且缺少本机凭据；不会接管账号或重置密码')
        credentials = {key: dict(username=fixture[field], password=secrets.token_urlsafe(15))
                       for key, field in [('demo', 'demo_username'), ('empty', 'empty_username')]}
        private_json(CREDENTIALS, credentials)
    checks = []
    with httpx.Client(base_url='http://127.0.0.1:8080', timeout=15, trust_env=False) as client:
        def api(method, path, token=None, body=None, status=200):
            response = client.request(method, path, headers={'Authorization': 'Bearer '+token} if token else {}, json=body)
            require(response.status_code == status, f'接口{path}状态{response.status_code}，预期{status}；未输出响应正文')
            if status != 200:
                return None
            envelope = response.json()
            require(envelope.get('code') == 0, f'接口{path}返回业务失败，未输出正文')
            return envelope.get('data')

        tokens, owners = {}, {}
        for key, field in [('demo', 'demo_username'), ('empty', 'empty_username')]:
            credential = credentials[key]
            require(credential['username'] == fixture[field], '私密凭据与测试账号名称不匹配')
            existing = db.rows("SELECT JSON_OBJECT('id',id,'role',role) FROM user WHERE username="+sql(credential['username'])+';')
            created = not existing
            if created:
                api('POST', '/api/auth/register', body=credential)
            else:
                require(existing[0]['role'] == 'STUDENT', '测试账号角色已改变，停止导入，不修改角色')
            tokens[key] = api('POST', '/api/auth/login', body=credential)['accessToken']
            me = api('GET', '/api/users/me', tokens[key])
            require(me['role'] == 'STUDENT', '测试账号必须是学生')
            owners[key] = int(me['id'])
            blank_profile = all(me.get(field) is None for field in ('background', 'examYear', 'targetMajor'))
            no_history = db.query(f'SELECT COUNT(*) FROM practice_record WHERE user_id={owners[key]};') == '0'
            if created or (blank_profile and no_history):
                api('PUT', '/api/users/profile', tokens[key], dict(targetMajor='081200', examYear=2027,
                    background=('【合成测试账号】'+fixture['notice']) if key == 'demo' else '【空数据测试账号】用于验证账号隔离，不代表真实考生。'))
        owner, empty_owner = owners['demo'], owners['empty']
        # Never attach another account's record to a fixture identifier.
        ids = [stable_id('task/'+t['code']) for t in fixture['tasks']]
        doc_ids = [stable_id('document/'+d['code']) for d in fixture['documents']]
        require(db.query('SELECT COUNT(*) FROM task WHERE id IN ('+','.join(sql(i) for i in ids)+f') AND user_id<>{owner};') == '0', '任务编号与其他账号冲突')
        require(db.query('SELECT COUNT(*) FROM personal_document WHERE id IN ('+','.join(sql(i) for i in doc_ids)+f') AND user_id<>{owner};') == '0', '文档编号与其他账号冲突')
        session_ids = ','.join(sql(s['id']) for s in fixture['sessions'])
        require(db.query(f'SELECT COUNT(*) FROM practice_record WHERE session_id IN ({session_ids}) AND user_id<>{owner};') == '0', '批次编号与其他账号冲突')
        def count_for(user):
            return {table: int(db.query(f'SELECT COUNT(*) FROM `{table}` WHERE user_id={user};')) for table in FEATURE_TABLES}

        before = count_for(owner)
        statement = insertion(fixture, questions, owner)
        require(db.query(statement) == '1', '未取得写入锁，本次数据未插入')
        after = count_for(owner)
        require(after == expected, '测试账号已存在其他操作或夹具数量不符；未覆盖已有记录，请核对备份')
        # Repeating the identical SQL must not create any duplicate rows.
        require(db.query(statement) == '1' and count_for(owner) == after, '重复执行校验失败')
        checks.append('数据库数量及重复执行无重复记录')
        require(all(n == 0 for n in count_for(empty_owner).values()), '空账号意外出现业务数据')
        token, empty_token = tokens['demo'], tokens['empty']
        overview = api('GET', '/api/stats/overview', token)
        answered = sum(a['user_answer'] is not None for a in records)
        correct = sum(a['is_correct'] == 1 for a in records)
        minutes = sum(v[2] for v in stats.values())
        require(overview['totalQuestions'] == answered and overview['totalCorrect'] == correct
                and overview['totalMinutes'] == minutes and overview['days'] == len(stats), '统计总览与模拟作答不一致')
        require(abs(overview['accuracy']-correct/answered) < 1e-8, '正确率与有效作答不一致')
        checks.append('统计：30次有效模拟作答、20次正确、2条未答不计入')
        ranges = api('GET', '/api/stats/range?from=2026-10-17&to=2026-10-23', token)
        require(len(ranges) == 7, '统计趋势日期不完整')
        checks.append('7天统计区间')
        sessions = api('GET', '/api/practice/sessions/page?pageNum=1&pageSize=3', token)
        require(sessions['total'] == 8 and len(sessions['list']) == 3, '练习分页不符')
        last_page = api('GET', '/api/practice/sessions/page?pageNum=3&pageSize=3', token)
        require(last_page['total'] == 8 and len(last_page['list']) == 2, '练习末页不符')
        checks.append('8批次分页及最后一页')
        review = api('GET', '/api/practice/sessions/fixture-20261023-day-1/review', token)
        require(review['total'] == 4 and all(r['snapshotStatus'] == 'AVAILABLE' for r in review['list']), '模拟作答快照不可回顾')
        checks.append('已答历史使用完整版本快照')
        partial = api('GET', '/api/practice/sessions/fixture-20261023-partial/review', token)
        require(sum(r['isCorrect'] is None for r in partial['list']) == 2, '未答项目数量不符')
        require(all(r.get('answer') is None for r in partial['list'] if r['isCorrect'] is None), '未答项目返回了答案')
        require(all(r['snapshotStatus'] == 'UNAVAILABLE' for r in partial['list'] if r['isCorrect'] is None),
                '待审核题目不应作为可继续练习题目返回')
        checks.append('未答无标准答案；待审核题不可继续作答')
        require(api('GET', '/api/questions/practice', token) == [], '待审核题目意外出现在学生抽题接口')
        checks.append('待审核题目未发布到学生抽题入口')
        wrong_page = api('GET', '/api/marks/wrong', token)
        favorite_page = api('GET', '/api/marks/favorite', token)
        require(wrong_page['total'] == len(wrong) and favorite_page['total'] == len(fixture['favorite_codes']), '错题或收藏数量不符')
        require(all(r['snapshotStatus'] == 'AVAILABLE' for r in wrong_page['list'] + favorite_page['list']), '错题或收藏历史快照不完整')
        checks.append('7道错题、6道收藏及历史快照')
        task_page = api('GET', '/api/tasks?pageNum=1&pageSize=20', token)
        require(task_page['total'] == 3 and {t['status'] for t in task_page['list']} == {'SUCCESS', 'FAILED', 'CANCELLED'}, '任务历史状态不符')
        checks.append('成功／失败／取消三种模拟任务历史')
        documents = api('GET', '/api/personal-documents', token)
        require(documents['total'] == 3, '个人文档数量不符')
        for doc, doc_id in zip(fixture['documents'], doc_ids, strict=True):
            current = api('GET', '/api/personal-documents/'+doc_id, token)
            versions = api('GET', '/api/personal-documents/'+doc_id+'/versions', token)
            require(current['version'] == len(doc['versions']) and current['content'] == doc['versions'][-1]
                    and versions['total'] == len(doc['versions']), '个人文档版本与正文不一致')
        checks.append('3份个人文档、6个版本及当前正文')
        for path in ['/api/marks/wrong', '/api/marks/favorite', '/api/practice/sessions/page', '/api/tasks', '/api/personal-documents']:
            require(api('GET', path, empty_token)['total'] == 0, '账号隔离失败：空账号看到其他账号列表')
        require(api('GET', '/api/stats/overview', empty_token)['totalQuestions'] == 0, '空账号统计被污染')
        for path in ['/api/personal-documents/'+doc_ids[0], '/api/tasks/'+ids[0], '/api/practice/sessions/fixture-20261023-day-1/review']:
            api('GET', path, empty_token, status=404)
        checks.append('跨账号列表为空、私有资源返回404')
        api('GET', '/api/questions/admin/pending', token, status=403)
        checks.append('学生不能访问管理审核接口')
    report = dict(batch=fixture['batch'], username=fixture['demo_username'], empty_username=fixture['empty_username'],
                  before=before, after=after, inserted={t: after[t]-before[t] for t in FEATURE_TABLES},
                  expected_statistics=dict(answered=answered,correct=correct,unanswered=2,minutes=minutes,days=7),
                  checks=checks, backup=str(backup), credentials_file=str(CREDENTIALS),
                  note='全部为独立测试账号中的合成记录；未调用模型，未审核发布题目。')
    private_json(output/'report.json', report)
    print(json.dumps(dict(inserted=report['inserted'], checks_passed=len(checks)), ensure_ascii=False), flush=True)
    print('执行记录：'+str(output), flush=True)
    print('私密登录信息文件：'+str(CREDENTIALS), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('失败：'+(str(error) if isinstance(error, RuntimeError) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
