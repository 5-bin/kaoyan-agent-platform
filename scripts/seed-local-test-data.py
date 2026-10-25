"""Preview by default; --apply backs up and adds only marked local test fixtures."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'scripts/fixtures/local-test-data.json'
TABLES = ('question', 'document', 'school', 'school_detail')
PRESERVED = ('user', 'task', 'practice_record', 'user_question_mark', 'study_stat', 'recommend_record')


def literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, int):
        return str(value)
    return 'CONVERT(0x' + value.encode('utf-8').hex() + ' USING utf8mb4)'


def source_locator(code):
    return 'scripts/fixtures/local-test-data.json#questions/' + code


def seed_sql(data):
    batch = literal(data['batch'])
    lock = "@fixture_lock=1"
    lines = ["SET NAMES utf8mb4;", "SELECT GET_LOCK('kaoyan_local_test_data_v1', 10) INTO @fixture_lock;", 'START TRANSACTION;']
    for order, q in enumerate(data['questions'], 1):
        columns = ['subject', 'knowledge_point', 'content', 'option_a', 'option_b', 'option_c', 'option_d',
                   'answer', 'analysis', 'difficulty', 'question_type', 'version', 'active', 'stable_order',
                   'review_status', 'source_type', 'source_name', 'source_locator', 'permission_note']
        values = [q['subject'], q['knowledge_point'], q['content'], *q['options'], q['answer'], q['analysis'],
                  q['difficulty'], 'SINGLE_CHOICE', 1, 1, order, 'PENDING_REVIEW', 'ORIGINAL', data['batch'],
                  source_locator(q['code']), '本项目新编本地测试夹具，非真题；尚待内容审核，不声明已获人工审核。']
        lines.append('INSERT INTO question (' + ','.join('`'+c+'`' for c in columns) + ') SELECT ' +
                     ','.join(literal(v) for v in values) + f' WHERE {lock} AND NOT EXISTS '
                     f'(SELECT 1 FROM question WHERE source_name={batch} AND source_locator={literal(source_locator(q["code"]))});')
    for d in data['documents']:
        values = [d['title'], d['subject'], d['content'], d['source_url'], 'PENDING_REVIEW']
        lines.append('INSERT INTO document (title,subject,content,source_url,status) SELECT ' +
                     ','.join(literal(v) for v in values) + f' WHERE {lock} AND NOT EXISTS '
                     f'(SELECT 1 FROM document WHERE title={literal(d["title"])});')
    for s in data['schools']:
        name = literal(s['name'])
        lines.append('INSERT INTO school (name,province,level) SELECT ' +
                     ','.join(literal(s[k]) for k in ('name', 'province', 'level')) + f' WHERE {lock} '
                     f'AND NOT EXISTS (SELECT 1 FROM school WHERE name={name});')
        for m in data['majors']:
            remark = literal('【完全虚构的测试数据】学校、层次与专业组合只用于列表及筛选测试；'
                             '招生人数与分数线未知，保留NULL。不是招生公告，不用于Agent条件推荐。批次：' + data['batch'])
            lines.append('INSERT INTO school_detail (school_id,major_name,major_code,year,enrollment_count,score_line,remark) '
                         f'SELECT s.id,{literal(m["major_name"])},{literal(m["major_code"])},{m["year"]},NULL,NULL,{remark} '
                         f'FROM school s WHERE s.name={name} AND {lock} AND NOT EXISTS '
                         f'(SELECT 1 FROM school_detail d WHERE d.school_id=s.id AND d.major_code={literal(m["major_code"])} AND d.year={m["year"]});')
    lines += ['SELECT @fixture_lock;', 'COMMIT;', "DO RELEASE_LOCK('kaoyan_local_test_data_v1');"]
    return '\n'.join(lines) + '\n'


def validate(data):
    assert len(data['questions']) == 16 and len(data['documents']) == 4 and len(data['schools']) == 6
    codes = [q['code'] for q in data['questions']]
    assert len(set(codes)) == len(codes)
    for q in data['questions']:
        assert q['subject'] in {'数据结构', '操作系统', '计算机网络', '计算机组成原理'}
        assert len(q['options']) == 4 and len(set(q['options'])) == 4 and q['answer'] in 'ABCD'
        assert q['content'].startswith('【测试自编题 ') and q['analysis']
        assert q['difficulty'] in {'EASY', 'MEDIUM', 'HARD'}
    assert all(s['name'].startswith('【测试虚构】') for s in data['schools'])
    assert all(d['title'].startswith('【测试资料】') and d['source_url'].startswith('https://') for d in data['documents'])
    by_code = {q['code']: q for q in data['questions']}
    assert by_code['DS01']['options'][ord(by_code['DS01']['answer'])-65] == ['A', 'B', 'C'].pop()
    assert by_code['DS02']['options'][ord(by_code['DS02']['answer'])-65] == ['A', 'B', 'C'].pop(0)
    assert int(by_code['DS04']['options'][ord(by_code['DS04']['answer'])-65]) == len(range(8))-1
    assert by_code['CO01']['options'][ord(by_code['CO01']['answer'])-65] == str(2**8)+'字节'
    assert int(by_code['CO02']['options'][ord(by_code['CO02']['answer'])-65]) == 2**10
    assert int(by_code['CO03']['options'][ord(by_code['CO03']['answer'])-65]) == int('101101', 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Back up the configured local database, then insert fixtures')
    args = parser.parse_args()
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    validate(data)
    sql = seed_sql(data)
    print('夹具校验通过：16道待审核自编题、4份待审核资料、6所虚构院校、12条虚构专业。')
    if not args.apply:
        print('预览完成，未连接数据库。添加 --apply 才会先备份再写入。')
        return
    values = dotenv_values(ROOT / '.env')
    host = values.get('DB_HOST') or '127.0.0.1'
    if host not in ('127.0.0.1', 'localhost', '::1'):
        raise RuntimeError('仅允许写入本机测试数据库')
    mysql, dump = shutil.which('mysql'), shutil.which('mysqldump')
    if not mysql or not dump:
        raise RuntimeError('缺少mysql或mysqldump，未写入')
    env = os.environ.copy()
    env['MYSQL_PWD'] = values.get('DB_PASSWORD') or ''
    common = ['--protocol=TCP', '--connect-timeout=5', '--default-character-set=utf8mb4', '-h', host,
              '-P', values.get('DB_PORT') or '3306', '-u', values.get('DB_USER') or '']
    database = values.get('DB_NAME') or 'kaoyan'

    def query(statement):
        result = subprocess.run([mysql, *common, '-N', '-B', database], input=statement,
                                env=env, text=True, encoding='utf-8', capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError('数据库执行失败，已隐藏原始连接信息；未提交的事务由连接关闭回滚')
        return result.stdout.strip()

    def preserved():
        return query('CHECKSUM TABLE ' + ','.join('`'+t+'`' for t in PRESERVED) + ';')

    def snapshot():
        return dict(line.split('\t') for line in query(' UNION ALL '.join(
            f"SELECT '{t}',COUNT(*) FROM `{t}`" for t in TABLES) + ';').splitlines())

    engine_rows = query('SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES '
                        'WHERE TABLE_SCHEMA=DATABASE();').splitlines()
    engines = dict(line.split('\t') for line in engine_rows)
    if any(engines.get(t) != 'InnoDB' for t in (*TABLES, *PRESERVED)):
        raise RuntimeError('缺少必要表或不是事务表，未写入')
    columns = set(query("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                        "AND TABLE_NAME='question';").splitlines())
    if not {'source_type', 'source_name', 'source_locator', 'permission_note'}.issubset(columns):
        raise RuntimeError('缺少V9字段，未写入；脚本不会自动迁移')
    before, unchanged_before = snapshot(), preserved()
    output = ROOT / '.cache' / ('test-data-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    backup = output / 'before.sql'
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as target:
        dump_options = [option for option in common if not option.startswith('--connect-timeout=')]
        result = subprocess.run([dump, *dump_options, '--single-transaction', '--no-tablespaces',
                                 '--set-gtid-purged=OFF', '--column-statistics=0', database],
                                env=env, stdout=target, stderr=subprocess.PIPE, timeout=60)
    if result.returncode or backup.stat().st_size == 0:
        raise RuntimeError('数据库备份失败，未执行任何插入')
    (output / 'insert.sql').write_text(sql, encoding='utf-8')
    result = query(sql)
    if result != '1':
        raise RuntimeError('未取得夹具锁，本次未写入')
    after = snapshot()
    if preserved() != unchanged_before:
        raise RuntimeError('账号或个人业务表校验值发生变化，需核对并发写入；保留备份，不自动恢复或删除')
    batch = literal(data['batch'])
    fixture_counts = query(
        f'SELECT COUNT(*) FROM question WHERE source_name={batch};'
        'SELECT COUNT(*) FROM document WHERE title IN (' + ','.join(literal(d['title']) for d in data['documents']) + ');'
        'SELECT COUNT(*) FROM school WHERE name IN (' + ','.join(literal(s['name']) for s in data['schools']) + ');'
        'SELECT COUNT(*) FROM school_detail d JOIN school s ON s.id=d.school_id WHERE s.name IN (' +
        ','.join(literal(s['name']) for s in data['schools']) + ');').splitlines()
    if fixture_counts != ['16', '4', '6', '12']:
        raise RuntimeError('插入后夹具数量与预期不同，已保留备份及SQL供检查')
    manifest = {'batch': data['batch'], 'before': before, 'after': after,
                'inserted': {t: int(after[t])-int(before[t]) for t in TABLES},
                'preserved_business_tables_unchanged': True,
                'backup': str(backup), 'fixture_counts': dict(zip(TABLES, map(int, fixture_counts)))}
    (output / 'report.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest['inserted'], ensure_ascii=False))
    print('账号及个人业务表校验值未变；备份和执行记录：' + str(output))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('失败：' + (str(error) if isinstance(error, RuntimeError) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
