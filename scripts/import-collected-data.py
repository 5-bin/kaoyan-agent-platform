"""Bounded, append-only import of a prepared collection-v3 manifest.

--inspect is read-only. --rehearse backs up the local database and restores an
independent copy. --apply additionally writes to kaoyan_dev ONLY after rehearsal.
The staging DDL is additive; no existing table, user record, RAG or .env is edited.
"""
import argparse
from collections import Counter
from datetime import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('collection_db_helpers', ROOT / 'scripts/import-real-data.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
sql, require = helper.sql, helper.require
STAGING = 'collection_import_record'
SCHEMA = '''CREATE TABLE collection_import_record (
 id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 record_type VARCHAR(16) COLLATE utf8mb4_bin NOT NULL,
 external_id VARCHAR(128) COLLATE utf8mb4_bin NOT NULL,
 external_version INT NOT NULL,
 content_sha256 CHAR(64) COLLATE ascii_bin NOT NULL,
 payload JSON NOT NULL,
 origin JSON NOT NULL,
 issues JSON NOT NULL,
 target_table VARCHAR(32) NULL,
 target_id BIGINT UNSIGNED NULL,
 imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uk_collection_identity(record_type,external_id,external_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;'''
ALLOWED = {
 'question': set('subject knowledge_point difficulty content option_a option_b option_c option_d answer analysis source_type source_year source_question_no permission_note source_locator source_name question_type version active stable_order review_status reviewer_user_id reviewed_at review_comment'.split()),
 'document': set('title subject content source_url status creator_user_id reviewer_user_id reviewed_at'.split())}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def load_manifest(path):
    manifest = json.loads(path.read_text())
    checksum = manifest.pop('manifestSha256')
    require(digest(manifest) == checksum, '准备清单校验和不符，请重新生成')
    manifest['manifestSha256'] = checksum
    require(manifest['format'] == 'collection-import-v1', '导入格式不符')
    for row in manifest['records']:
        require(row['kind'] in ('来源', '院校', '招生专业', '知识资料', '题目'), '非法采集类型')
        require(digest(row['payload']) == row['contentSha256'], '原始记录校验和不符')
        target = row['target']
        if target:
            table, values = target['table'], target['values']
            require(table in ALLOWED and set(values) == ALLOWED[table], '业务表或字段不在白名单')
            require(values.get('review_status', 'PENDING_REVIEW') == 'PENDING_REVIEW'
                    and values.get('status', 'DRAFT') == 'DRAFT'
                    and values['reviewer_user_id'] is None and values['reviewed_at'] is None,
                    '禁止导入发布状态或审核身份')
    return manifest


def key(row):
    return (row['kind'], row['externalId'], row['externalVersion'])


def condition(row):
    return (f'record_type={sql(row["kind"])} AND external_id={sql(row["externalId"])} '
            f'AND external_version={sql(row["externalVersion"])}')


def inspect(db, manifest):
    table_names = db.tables()
    staged = db.records(STAGING) if STAGING in table_names else []
    known = {(r['record_type'], r['external_id'], r['external_version']): r for r in staged}
    for row in staged:
        payload = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
        require(digest(payload) == row['content_sha256'], '暂存记录内容与登记摘要不符，停止操作')
    for row in manifest['records']:
        old = known.get(key(row))
        require(not old or old['content_sha256'] == row['contentSha256'], '同编号、同版本存在内容冲突：' + row['externalId'])
    existing = {t: db.records(t) for t in ('question', 'document', 'school')}
    q_keys = {tuple(str(r.get(c) or '').strip() for c in ('subject', 'content', 'option_a', 'option_b', 'option_c', 'option_d'))
              for r in existing['question']}
    doc_keys = {(r['subject'], r['title']) for r in existing['document']}
    for row in manifest['records']:
        if key(row) in known or not row['target']:
            continue
        target = row['target']; values = target['values']
        if target['table'] == 'question':
            identity = tuple(str(values.get(c) or '').strip() for c in ('subject', 'content', 'option_a', 'option_b', 'option_c', 'option_d'))
            require(identity not in q_keys, '与库中题目重复，需先建立人工映射：' + row['externalId'])
            q_keys.add(identity)
        else:
            identity = (values['subject'], values['title'])
            require(identity not in doc_keys, '与库中资料标题重复，需先核对：' + row['externalId'])
            doc_keys.add(identity)
    return {'database': db.name, 'stagingTableExists': STAGING in table_names,
            'rawRowsToInsert': sum(key(r) not in known for r in manifest['records']),
            'existingIdenticalStagingRows': sum(key(r) in known for r in manifest['records']),
            'businessRowsToInsert': dict(Counter(r['target']['table'] for r in manifest['records']
                if r['target'] and key(r) not in known)),
            'schoolsAlreadyInPublicTable': sum(r['payload']['fields']['name'] in {s['name'] for s in existing['school']}
                for r in manifest['records'] if r['kind'] == '院校'),
            'existingPublicCounts': {t: len(v) for t, v in existing.items()}}


def ensure_schema(db):
    if STAGING not in db.tables():
        db.query(SCHEMA)
    require(set(db.columns(STAGING)) == set('id record_type external_id external_version content_sha256 payload origin issues target_table target_id imported_at'.split()),
            '暂存表结构不符，停止操作')


def statement(db, manifest, before, rollback=False, failure=False):
    lines = ["SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION';",
             'CREATE TEMPORARY TABLE collection_guard(v INT NOT NULL CHECK(v=1));',
             "INSERT INTO collection_guard VALUES(IF(GET_LOCK('kaoyan_collection_import_v1',10)=1,1,0));",
             'SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;', 'START TRANSACTION;']
    for table in ('question', 'document', STAGING):
        expression = db.fingerprint_expression(table)
        lines.append(f'SELECT id FROM `{table}` ORDER BY id FOR UPDATE;')
        fingerprints = before[table]
        lines.append(f'INSERT INTO collection_guard SELECT IF(COUNT(*)={len(fingerprints)},1,0) FROM `{table}`;')
        for line in fingerprints:
            primary, fingerprint = line.split('\t')
            primary_id = json.loads(primary)[0]
            lines.append('INSERT INTO collection_guard SELECT IF(COUNT(*)=1,1,0) FROM `'+table+'` WHERE id='+sql(primary_id)+
                         ' AND '+expression+'='+sql(fingerprint)+';')
    for row in manifest['records']:
        where = condition(row)
        lines.append('INSERT INTO collection_guard SELECT IF(COUNT(*)=0,1,0) FROM '+STAGING+' WHERE '+where+
                     ' AND content_sha256<>'+sql(row['contentSha256'])+';')
        origin = {**row['origin'], 'workbookSha256': next(f['sha256'] for f in manifest['files'] if f['path'] == row['origin']['file'])}
        columns = ('record_type', 'external_id', 'external_version', 'content_sha256', 'payload', 'origin', 'issues')
        values = (row['kind'], row['externalId'], row['externalVersion'], row['contentSha256'],
                  canonical(row['payload']), canonical(origin), canonical({'entryErrors': row['entryErrors'], 'publishBlockers': row['issues']}))
        lines.append('INSERT INTO '+STAGING+'('+','.join(columns)+') SELECT '+','.join(sql(v) for v in values)+
                     ' WHERE NOT EXISTS(SELECT 1 FROM '+STAGING+' WHERE '+where+');')
        lines.append('SET @collection_is_new=ROW_COUNT();')
        if row['target']:
            table, values = row['target']['table'], row['target']['values']
            lines.append('INSERT INTO `'+table+'`('+','.join('`'+k+'`' for k in values)+') SELECT '+
                         ','.join(sql(v) for v in values.values())+' WHERE @collection_is_new=1;')
            lines.append('UPDATE '+STAGING+' SET target_table='+sql(table)+',target_id=LAST_INSERT_ID() WHERE '+where+
                         ' AND @collection_is_new=1;')
    if failure:
        lines.append('INSERT INTO collection_guard VALUES(0);')
    lines += ['ROLLBACK;' if rollback else 'COMMIT;', "SELECT RELEASE_LOCK('kaoyan_collection_import_v1');"]
    return '\n'.join(lines) + '\n'


def validate_result(db, manifest, before):
    after = db.snapshot()
    for table, old in before.items():
        now = dict(line.split('\t') for line in after[table])
        require(all(now.get(k) == v for k, v in (line.split('\t') for line in old)), '原有行发生变化：'+table)
        if table not in ('question', 'document', STAGING):
            require(old == after[table], '非导入表发生变化：'+table)
    mapped = db.records(STAGING)
    wanted = {key(r): r for r in manifest['records']}
    verified = Counter()
    for row in mapped:
        record = wanted.get((row['record_type'], row['external_id'], row['external_version']))
        if not record:
            continue
        payload = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
        require(payload == record['payload'], '暂存原值与正文不一致')
        if record['target']:
            target = record['target']
            require(row['target_table'] == target['table'] and row['target_id'], '目标映射缺失')
            saved = db.records(row['target_table'], 'id='+sql(row['target_id']))
            require(len(saved) == 1 and all(saved[0][k] == v for k, v in target['values'].items()), '业务行字段不符')
            verified[row['target_table']] += 1
        else:
            require(row['target_id'] is None, '不应转换的条目存在业务映射')
    require(sum(1 for row in mapped if (row['record_type'], row['external_id'], row['external_version']) in wanted) == len(wanted), '暂存数量不符')
    return {'allOriginalRowsUnchanged': True, 'verifiedTargets': dict(verified),
            'counts': {t: len(v) for t, v in after.items() if t in ('question', 'document', 'school', 'school_detail', STAGING)}}


def run(manifest, apply=False):
    db = helper.Database()
    plan = inspect(db, manifest)
    require(db.query('SELECT DISTINCT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE();') == 'InnoDB', '存在非事务表')
    base = ROOT / '.cache/collection-import-20261028'
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(base, 0o700)
    with (base / 'operation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        output = base / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        output.mkdir(mode=0o700)
        before = db.snapshot()
        backup = db.backup(output)
        require(before == db.snapshot(), '备份期间数据变化，停止操作')
        clone_name = 'kaoyan_realdata_verify_' + secrets.token_hex(6)
        db.query(f'CREATE DATABASE `{clone_name}` CHARACTER SET utf8mb4;', server=True)
        clone = helper.Database(clone_name)
        clone.query(backup.read_text(), timeout=120)
        require(clone.snapshot() == before, '备份恢复摘要不一致')
        ensure_schema(clone)
        clone_before = clone.snapshot()
        sql_text = statement(clone, manifest, clone_before, failure=True)
        try:
            clone.query(sql_text, timeout=120)
        except RuntimeError:
            pass
        else:
            raise RuntimeError('失败注入未触发')
        require(clone.snapshot() == clone_before, '失败事务未回滚')
        clone.query(statement(clone, manifest, clone_before, rollback=True), timeout=120)
        require(clone.snapshot() == clone_before, '显式回滚改变了已有行')
        clone.query(statement(clone, manifest, clone_before), timeout=120)
        validation = validate_result(clone, manifest, clone_before)
        once = clone.snapshot()
        clone.query(statement(clone, manifest, once), timeout=120)
        require(clone.snapshot() == once, '重复导入修改了已有行')
        report = {'applied': False, 'targetDatabase': db.name, 'plan': plan, 'manifestSha256': manifest['manifestSha256'],
                  'restoreDatabase': clone_name, 'backup': str(backup), 'restoreVerifiedTables': len(before),
                  'failureRollbackVerified': True, 'explicitRollbackVerified': True, 'repeatedImportUnchanged': True,
                  'isolatedValidation': validation, 'modelCalls': 0, 'applicationServicesStarted': False}
        helper.dump(output / 'rehearsal.json', report)
        if apply:
            require(db.snapshot() == before, '预演期间日常库变化，请重新检查')
            inspect(db, manifest)
            ensure_schema(db)  # Additive DDL is not rollbackable; retained on a later transaction failure.
            guarded_before = db.snapshot()
            final_sql = statement(db, manifest, guarded_before)
            helper.write_private(output / 'apply.sql', final_sql)
            db.query(final_sql, timeout=120)
            report['dailyValidation'] = validate_result(db, manifest, guarded_before)
            report['applied'] = True
        helper.dump(output / 'report.json', report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--inspect', action='store_true')
    mode.add_argument('--rehearse', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        if args.inspect:
            print(json.dumps(inspect(helper.Database(), manifest), ensure_ascii=False))
        else:
            run(manifest, apply=args.apply)
    except Exception as e:
        print('导入停止：' + (str(e) if isinstance(e, (ValueError, RuntimeError)) else type(e).__name__), file=sys.stderr)
        sys.exit(1)
