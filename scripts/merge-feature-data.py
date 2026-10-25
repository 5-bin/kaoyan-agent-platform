"""Merge public 2027 fixtures into the local development database; preview by default.

Never copies accounts, roles, credentials or personal histories from the isolated DB.
Existing natural keys are preserved, including subsequent manual edits/reviews.
"""
import argparse
from datetime import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

from dotenv import dotenv_values, set_key

from feature_env import ROOT, require, sql


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


local_seed = module('local_feature_history_seed', 'seed-feature-test-data.py')
fixture_seed = module('public_feature_fixtures', 'feature-test.py')
PUBLIC = ('school', 'school_detail', 'question', 'document')
CORPUS = ROOT / 'kaoyan-agent/knowledge/feature-2027-corpus.json'
PRIVATE = ROOT / '.cache/development-data-merge'
NOTE = '2026-10-23按用户授权迁入本机日常开发库，用于功能测试；沿用自动测试审核状态，不代表人工审核或正式题库发布。'


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as target:
        target.write(value)


def corpus_records(schools):
    original = json.loads((ROOT / 'kaoyan-agent/knowledge/corpus.json').read_text())
    records = [d for d in original if d['domain'] == 'knowledge']
    for p in schools['programs']:
        keys = ('programId', 'school', 'college', 'major', 'majorCode', 'year', 'degreeType',
                'region', 'studyMode', 'examSubjects')
        metadata = {k: p[k] for k in keys}
        metadata['updatedAt'] = p['retrievedAt']
        content = (f'{p["school"]}{p["college"]}2027年全日制{p["major"]}（{p["majorCode"]}），'
                   f'{"学术学位" if p["degreeType"] == "academic" else "专业学位"}，初试代码为'
                   + '、'.join(p['examSubjects']) + '。' + p['note'] + '未收录招生人数、分数线或录取概率。')
        records.append(dict(id=p['programId'], domain='school', title=f'{p["school"]}2027年{p["major"]}核验摘要',
                            url=p['sourceUrl'], locator=p['locator'], version=p['version'],
                            retrievedAt=p['retrievedAt'], license=p['license'], reviewStatus='verified',
                            content=content, metadata=metadata, keywords=[p['school'], p['majorCode']]))
    return records


def rows_to_insert(questions, schools, corpus):
    """Return table, values and natural key; no source DB IDs cross environments."""
    result = []
    for s in schools['schools']:
        result.append(('school', dict(name=s['name'], province=s['province'], level=s['level']),
                       'name=' + sql(s['name'])))
    for p in schools['programs']:
        school_id = '(SELECT id FROM school WHERE name=' + sql(p['school']) + ')'
        remark = (f'【2027官方来源核验摘要】{p["college"]}；'
                  + ('学硕' if p['degreeType'] == 'academic' else '专硕') + '；全日制；初试：'
                  + '、'.join(p['examSubjects']) + f'。{p["note"]} 来源：{p["sourceUrl"]}；'
                  + f'定位：{p["locator"]}；核验：{p["retrievedAt"]}；版本：{p["version"]}；权限：{p["license"]}')
        values = dict(school_id=None, major_name=p['major'], major_code=p['majorCode'], year=2027,
                      enrollment_count=None, score_line=None, remark=remark)
        key = f'school_id={school_id} AND major_code={sql(p["majorCode"])} AND year=2027 AND major_name={sql(p["major"])}'
        result.append(('school_detail', values, key))
    for order, q in enumerate(questions, 1):
        values = dict(subject=q['subject'], knowledge_point=q['knowledgePoint'], content=q['content'],
                      **dict(zip(('option_a', 'option_b', 'option_c', 'option_d'), q['options'])),
                      answer=q['answer'], analysis=q['analysis'], difficulty=q['difficulty'],
                      question_type='SINGLE_CHOICE', version=1, active=q['targetActive'], stable_order=order,
                      review_status=q['targetStatus'], reviewer_user_id=None, reviewed_at=None,
                      review_comment=NOTE if q['targetStatus'] != 'PENDING_REVIEW' else None,
                      source_type=q['sourceType'], source_name=q['sourceName'], source_locator=q['sourceLocator'],
                      permission_note='本项目原创功能测试题，非历年真题。' + NOTE)
        result.append(('question', values, f'source_name={sql(q["sourceName"])} AND source_locator={sql(q["sourceLocator"])}'))
    for d in (x for x in corpus if x['domain'] == 'knowledge'):
        values = dict(title='【功能测试资料】' + d['title'], subject=d['subject'],
                      content=d['content'] + f'\n\n来源：{d["url"]}\n定位：{d["locator"]}\n'
                      + f'版本：{d["version"]}；原核验日期：{d["retrievedAt"]}\n{d["license"]}\n' + NOTE,
                      source_url=d['url'], status='PUBLISHED', creator_user_id=None, reviewer_user_id=None,
                      reviewed_at=None)
        result.append(('document', values, 'title=' + sql(values['title'])))
    return result


def insertion(rows):
    statements = ["SET NAMES utf8mb4; SELECT GET_LOCK('kaoyan_merge_public_2027',10) INTO @merge_lock;", 'START TRANSACTION;']
    for table, values, key in rows:
        encoded = [sql(v) for v in values.values()]
        if table == 'school_detail':
            encoded[0] = key.split(' AND major_code=')[0].removeprefix('school_id=')
        statements.append(f'INSERT INTO `{table}` (' + ','.join('`' + k + '`' for k in values)
                          + ') SELECT ' + ','.join(encoded)
                          + f' WHERE @merge_lock=1 AND NOT EXISTS (SELECT 1 FROM `{table}` WHERE {key});')
    statements += ['COMMIT;', 'SELECT @merge_lock;', "DO RELEASE_LOCK('kaoyan_merge_public_2027');"]
    return '\n'.join(statements) + '\n'


def table_names(db):
    return db.query('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME;').splitlines()


def fingerprint(db, table, max_id=None):
    condition = '' if max_id is None else ' WHERE id <= ' + str(max_id)
    # Raw rows are hashed in memory, never printed or included in the public report.
    return hashlib.sha256(db.query(f'SELECT * FROM `{table}`{condition} ORDER BY 1;').encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--database', default='kaoyan_dev', help='Must match the local .env DB_NAME')
    args = parser.parse_args()
    questions, schools = fixture_seed.fixtures()
    records = corpus_records(schools)
    rows = rows_to_insert(questions, schools, records)
    print('合并预览：10校、15专业、160可练习题、12审核样例、4份公共短摘要；保留已有记录。')
    if not args.apply:
        print('未连接数据库、未更改配置；--apply 才执行备份、补齐V12、事务补缺和配置切换。')
        return
    config = dotenv_values(ROOT / '.env')
    require(config.get('DB_NAME') == args.database == 'kaoyan_dev', '仅允许明确配置的本机kaoyan_dev日常开发库')
    require(not config.get('SPRING_DATASOURCE_URL'), '存在数据源覆盖，请先核对实际目标库')
    require(config.get('RAG_BACKEND', 'lexical') in (None, '', 'lexical'), '向量模式需先构建新索引，不自动切换')
    configured_corpus = config.get('RAG_DATA')
    require(not configured_corpus or Path(configured_corpus) == CORPUS, '已有自定义RAG_DATA，拒绝覆盖')
    if CORPUS.exists():
        require(json.loads(CORPUS.read_text()) == records, '语料文件有人工修改，拒绝覆盖')
    db = local_seed.Database()
    existing = table_names(db)
    require(set(PUBLIC).issubset(existing), '缺少业务表；本脚本不执行V1或旧种子')
    engines = db.rows("SELECT JSON_OBJECT('name',TABLE_NAME,'engine',ENGINE) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE();")
    require(all(t['engine'] == 'InnoDB' for t in engines), '存在非事务表，停止合并')
    for table, _, key in rows:
        require(int(db.query(f'SELECT COUNT(*) FROM `{table}` WHERE {key};')) <= 1,
                '自然键重复，停止合并：' + table)
    privacy_tables = {'assistant_privacy', 'assistant_action'}
    require(not (privacy_tables & set(existing)) or privacy_tables.issubset(existing), 'V12结构不完整，停止自动处理')
    PRIVATE.mkdir(parents=True, mode=0o700, exist_ok=True)
    with (PRIVATE / 'operation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        output = PRIVATE / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        output.mkdir(mode=0o700)
        db.backup(output)
        fd = os.open(output / 'before.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as out:
            out.write((ROOT / '.env').read_bytes())
        previous = {t: int(db.query(f'SELECT COALESCE(MAX(id),0) FROM `{t}`;')) for t in PUBLIC}
        original_hashes = {t: fingerprint(db, t, previous[t]) if t in PUBLIC else fingerprint(db, t) for t in existing}
        before = {t: int(db.query(f'SELECT COUNT(*) FROM `{t}`;')) for t in PUBLIC}
        migration = ROOT / 'kaoyan-B/src/main/resources/db/V12__assistant_privacy.sql'
        applied_v12 = not privacy_tables.issubset(existing)
        if applied_v12:
            db.query(migration.read_text())
        statement = insertion(rows)
        write_private(output / 'insert.sql', statement)
        require(db.query(statement) == '1', '未取得合并锁，未执行数据插入')
        require(all(fingerprint(db, t, previous[t]) == original_hashes[t] if t in PUBLIC
                    else fingerprint(db, t) == original_hashes[t] for t in existing),
                '已有记录校验值变化，请检查并发操作；备份保留，不自动恢复整库')
        after = {t: int(db.query(f'SELECT COUNT(*) FROM `{t}`;')) for t in PUBLIC}
        require(all(db.query(f'SELECT COUNT(*) FROM `{t}` WHERE {key};') == '1' for t, _, key in rows), '合并后的自然键不完整')
        db.query(statement)
        require({t: int(db.query(f'SELECT COUNT(*) FROM `{t}`;')) for t in PUBLIC} == after, '重复执行意外新增记录')
        if not CORPUS.exists():
            with CORPUS.open('x', encoding='utf-8') as target:
                json.dump(records, target, ensure_ascii=False, indent=2)
                target.write('\n')
        # Do not rewrite provider settings, passwords, model switches or DB connection.
        if config.get('RAG_DATA') != str(CORPUS):
            set_key(ROOT / '.env', 'RAG_DATA', str(CORPUS), quote_mode='never')
        inserted_ids = {t: db.query(f'SELECT id FROM `{t}` WHERE id>{previous[t]} ORDER BY id;').splitlines() for t in PUBLIC}
        report = dict(database=db.name, before=before, after=after,
                      inserted={t: after[t] - before[t] for t in PUBLIC}, inserted_ids=inserted_ids,
                      all_existing_records_unchanged=True, repeated_sql_inserted_zero=True,
                      applied_v12=applied_v12, migration_sha256=hashlib.sha256(migration.read_bytes()).hexdigest(),
                      corpus=str(CORPUS), personal_data_imported=False, services_started=False,
                      note=NOTE)
        write_private(output / 'report.json', json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(dict(inserted=report['inserted'], applied_v12=applied_v12,
                              all_existing_records_unchanged=True, repeated_sql_inserted_zero=True), ensure_ascii=False))
        print('备份、SQL、插入ID与报告：' + str(output))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('失败：' + (str(error) if isinstance(error, RuntimeError) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
