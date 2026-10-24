"""Replace identified demo fixtures with reviewed source-backed local data.

Default: offline preview. --inspect: read-only DB plan. --apply: private backup,
restore verification, isolated rehearsal + rollback check, then one guarded
transaction in kaoyan_dev. Never runs V1, grants roles, or resets auto IDs.
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
import shutil
import subprocess
import sys

from dotenv import dotenv_values, set_key
sys.path.insert(0, str(Path(__file__).resolve().parent))
from real_data_catalog import ROOT, DATE, SOURCE_NAME, questions, documents

PRIVATE = ROOT / '.cache/real-data-20261024'
TARGET = 'kaoyan_dev'
LEGACY_SOURCES = ('local-test-data-v1-20261022', 'feature-test-2027-v1')


def require(ok, message):
    if not ok: raise RuntimeError(message)


def sql(value):
    if value is None: return 'NULL'
    if isinstance(value, (int,float)): return str(value)
    return "CONVERT(0x"+str(value).encode().hex()+" USING utf8mb4)"


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/filename)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def write_private(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f: f.write(text)


def dump(path, value):
    write_private(path, json.dumps(value, ensure_ascii=False, indent=2)+'\n')


class Database:
    def __init__(self, name=TARGET):
        values = dotenv_values(ROOT/'.env')
        require(values.get('DB_NAME') == TARGET, '根.env必须明确指向kaoyan_dev')
        require(values.get('DB_HOST','127.0.0.1') in ('localhost','127.0.0.1','::1'), '只允许本机数据库')
        require(not values.get('SPRING_DATASOURCE_URL'), '存在数据源URL覆盖，停止操作')
        require(re.fullmatch(r'kaoyan_dev|kaoyan_realdata_verify_[a-f0-9]{12}',name), '数据库边界不符')
        self.name, self.values = name, values
        self.env = os.environ.copy(); self.env['MYSQL_PWD'] = values.get('DB_PASSWORD') or ''
        self.options=['--protocol=TCP','--default-character-set=utf8mb4','-h',values.get('DB_HOST') or '127.0.0.1',
            '-P',values.get('DB_PORT') or '3306','-u',values.get('DB_USER') or '']
        require(shutil.which('mysql') and shutil.which('mysqldump'), '缺少mysql或mysqldump')

    def query(self, statement, server=False, timeout=90):
        command=['mysql',*self.options,'--connect-timeout=5','-N','-B','--raw']
        if not server: command.append(self.name)
        p=subprocess.run(command,input=statement,env=self.env,text=True,capture_output=True,timeout=timeout)
        if p.returncode:
            # Only error numbers are safe to print; SQL can contain private data.
            codes=re.findall(r'ERROR (\d+)',p.stderr)
            raise RuntimeError('MySQL操作失败，错误编号 '+','.join(codes)+'；凭据及原始SQL未输出，未提交事务会回滚')
        return p.stdout.strip()

    def rows(self, statement):
        return [json.loads(line) for line in self.query(statement).splitlines() if line]

    def records(self, table, where='1=1'):
        columns=self.columns(table)
        fields=','.join(sql(c)+',`'+c+'`' for c in columns)
        return self.rows(f'SELECT JSON_OBJECT({fields}) FROM `{table}` WHERE {where} ORDER BY '+','.join('`'+c+'`' for c in self.keys(table))+';')

    def tables(self):
        return self.query('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME;').splitlines()

    def columns(self, table):
        require(re.fullmatch('[a-z_]+',table), '非法表名')
        return self.query('SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+sql(table)+' ORDER BY ORDINAL_POSITION;').splitlines()

    def keys(self, table):
        return self.query('SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+sql(table)+" AND CONSTRAINT_NAME='PRIMARY' ORDER BY ORDINAL_POSITION;").splitlines()

    def fingerprint_expression(self, table):
        return 'SHA2(CAST(JSON_ARRAY('+','.join('`'+c+'`' for c in self.columns(table))+') AS CHAR),256)'

    def fingerprint(self, table, where='1=1'):
        keys=self.keys(table); require(keys,'业务表缺少主键')
        return self.query('SELECT CAST(JSON_ARRAY('+','.join('`'+c+'`' for c in keys)+') AS CHAR),'+self.fingerprint_expression(table)+f' FROM `{table}` WHERE {where} ORDER BY '+','.join('`'+c+'`' for c in keys)+';').splitlines()

    def snapshot(self):
        return {t:self.fingerprint(t) for t in self.tables()}

    def backup(self, output):
        path=output/'before.sql'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:
            p=subprocess.run(['mysqldump',*self.options,'--single-transaction','--no-tablespaces',
                '--set-gtid-purged=OFF','--column-statistics=0','--hex-blob',self.name],env=self.env,stdout=f,stderr=subprocess.PIPE,timeout=120)
        require(p.returncode==0 and path.stat().st_size>0,'完整备份失败，未执行清理')
        return path


def schools():
    source=json.loads((ROOT/'scripts/fixtures/feature-2027-schools.json').read_text())
    checks=json.loads((ROOT/'scripts/fixtures/real-schools-verification-20261024.json').read_text())
    source['batch']='real-official-schools-20261024'
    for p in source['programs']:
        if p['schoolCode'] in checks['rechecked']:
            p['retrievedAt']=DATE
            p['version']='official-2027-recheck-20261024'
        else:
            p['note']+=' 本次动态专业目录不可访问；保留2026-10-23核验日期与证据，未重新核验。'
    return source


def corpus():
    records=documents()
    for p in schools()['programs']:
        metadata={k:p[k] for k in ('programId','school','college','major','majorCode','year','degreeType','region','studyMode','examSubjects')}
        metadata['updatedAt']=p['retrievedAt']
        content=(p['school']+p['college']+'2027年全日制'+p['major']+'（'+p['majorCode']+'），'
            +('学术学位' if p['degreeType']=='academic' else '专业学位')+'，初试代码为'+'、'.join(p['examSubjects'])+'。'+p['note']+'未收录招生人数与复试线。')
        records.append(dict(id=p['programId'],domain='school',title=p['school']+'2027年'+p['major']+'招生核验摘要',
            url=p['sourceUrl'],locator=p['locator'],version=p['version'],retrievedAt=p['retrievedAt'],
            license=p['license'],reviewStatus='verified',content=content,metadata=metadata,keywords=[p['school'],p['majorCode']]))
    return records


def question_values(q, order):
    keep=('subject','knowledge_point','content','answer','analysis','difficulty','source_type','source_name','source_locator','source_question_no','permission_note')
    result={k:q[k] for k in keep}
    result.update(dict(zip(('option_a','option_b','option_c','option_d'),q['options'])))
    result.update(question_type='SINGLE_CHOICE',version=1,active=1,stable_order=order,review_status='APPROVED',
        reviewer_user_id=None,review_comment=DATE+'本次导入核验：'+q['review_method'],source_year=None)
    # The actual execution time replaces this value; never invent a reviewer.
    result['reviewed_at']=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return result


def document_values(d):
    footer=(f'\n\n来源：{d["url"]}\n原文定位：{d["locator"]}\n版本：{d["version"]}\n获取及核对日期：{d["retrievedAt"]}\n使用许可：{d["license"]}\n中文节选整理，不替代完整教材。')
    return dict(title=d['title'],subject=d['subject'],content=d['content']+footer,source_url=d['url'],status='PUBLISHED',
        creator_user_id=None,reviewer_user_id=None,reviewed_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


def stable_id(code):
    from uuid import uuid5,NAMESPACE_URL
    return str(uuid5(NAMESPACE_URL,'kaoyan-feature-test-v1-20261023/'+code))


def id_condition(ids, field='id'):
    return field+' IN ('+','.join(sql(i) for i in ids)+')' if ids else '0=1'


def deletion_plan(db):
    local=json.loads((ROOT/'scripts/fixtures/local-test-data.json').read_text())
    feature=json.loads((ROOT/'scripts/fixtures/feature-2027-questions.json').read_text())
    expected={('local-test-data-v1-20261022','scripts/fixtures/local-test-data.json#questions/'+q['code']):q for q in local['questions']}
    for q in feature:
        expected[(q['sourceName'],q['sourceLocator'])]={**q,'knowledge_point':q['knowledgePoint']}
    old=db.records('question','source_name IN ('+','.join(sql(s) for s in LEGACY_SOURCES)+')')
    for q in old:
        e=expected.get((q['source_name'],q['source_locator']))
        require(e is not None and all(q[k]==e[k] for k in ('subject','knowledge_point','content','answer','analysis','difficulty'))
            and [q['option_'+c] for c in 'abcd']==e['options'],'测试题已被人工修改或来源不匹配，停止清理')
    require(len(old) in (0,188),'测试题数量改变，请重新核对清理清单')
    fake_names={s['name']:s for s in local['schools']}
    fake=db.records('school','name IN ('+','.join(sql(n) for n in fake_names)+')')
    require(len(fake) in (0,6),'虚构院校数量改变，停止清理')
    for s in fake:
        require(all(s[k]==fake_names[s['name']][k] for k in ('province','level')),'虚构院校有人工修改，停止清理')
    details=db.records('school_detail',id_condition([s['id'] for s in fake],'school_id'))
    require(len(details) in (0,12),'虚构专业数量改变，停止清理')
    for d in details:
        require(d['year']==2027 and '虚构' in d['remark'] and d['enrollment_count'] is None and d['score_line'] is None,'虚构专业内容被修改，停止清理')
    require(db.query('SELECT COUNT(*) FROM recommend_record WHERE '+id_condition([s['id'] for s in fake],'school_id')+';')=='0','虚构院校已有关联推荐，不自动删除')
    # Exact document content checks protect subsequent edits.
    merge=module('legacy_public_merge','merge-feature-data.py')
    merged=merge.rows_to_insert(feature,json.loads((ROOT/'scripts/fixtures/feature-2027-schools.json').read_text()),merge.corpus_records(json.loads((ROOT/'scripts/fixtures/feature-2027-schools.json').read_text())))
    doc_expected={d['title']:d for d in local['documents']}
    doc_expected.update({v['title']:v for t,v,_ in merged if t=='document'})
    old_docs=db.records('document','title IN ('+','.join(sql(t) for t in doc_expected)+')')
    require(len(old_docs) in (0,8),'演示资料数量改变，停止清理')
    for d in old_docs:
        e=doc_expected[d['title']]
        require(all(d[k]==e[k] for k in ('subject','content','source_url')) and d['creator_user_id'] is None,'演示资料有人工修改，停止清理')
    result={t:[] for t in ('question','school','school_detail','document','practice_record','user_question_mark','study_stat','task','personal_document','personal_document_version')}
    result.update(question=old,school=fake,school_detail=details,document=old_docs)
    qids=[q['id'] for q in old]
    result['practice_record']=db.records('practice_record',id_condition(qids,'question_id'))
    result['user_question_mark']=db.records('user_question_mark',id_condition(qids,'question_id'))
    days={(r['user_id'],(r['answered_at'] or r['created_at'])[:10]) for r in result['practice_record']}
    for uid,day in sorted(days):
        where=f'user_id={uid} AND stat_date={sql(day)}'
        remaining=db.query(f'SELECT COUNT(*) FROM practice_record WHERE user_id={uid} AND DATE(COALESCE(answered_at,created_at))={sql(day)} AND NOT ({id_condition(qids,"question_id")});')
        require(remaining=='0','同日统计含其他题目作答，拒绝自动清理混合统计')
        result['study_stat']+=db.records('study_stat',where)
    fixture=json.loads((ROOT/'scripts/fixtures/feature-test-data.json').read_text())
    users=db.records('user','username='+sql(fixture['demo_username']))
    kept=[]
    if users:
        owner=users[0]['id']
        for t in fixture['tasks']:
            stored=db.records('task','id='+sql(stable_id('task/'+t['code'])))
            if not stored: continue
            row=stored[0]
            payload=row['input_payload'];payload=json.loads(payload) if isinstance(payload,str) else payload
            output=row['result_payload'];output=json.loads(output) if isinstance(output,str) else output
            expected_output=None if t['status']!='SUCCESS' else dict(outcome='NEEDS_INPUT',explanationMode='rules',resolvedTaskType='KNOWLEDGE_QA',answer=t['answer'],references=[],releaseId=fixture['batch'],notice='合成任务历史，不是实际模型调用或检索结果。')
            if (row['user_id']==owner and payload==dict(query=t['query'],fixture=fixture['batch']) and row['status']==t['status']
                    and output==expected_output and row['error_message']==t.get('error') and row['release_id']==fixture['batch']):
                result['task'].append(row)
            else: kept.append('人工变更的原模拟任务 '+row['id'])
        for d in fixture['documents']:
            did=stable_id('document/'+d['code'])
            stored=db.records('personal_document','id='+sql(did));versions=db.records('personal_document_version','document_id='+sql(did))
            if not stored: continue
            row=stored[0]
            same=(row['user_id']==owner and row['title']==d['title'] and row['content']==d['versions'][-1] and row['version']==len(d['versions']) and len(versions)==len(d['versions']))
            same=same and all(1<=v['version']<=len(d['versions']) and v['user_id']==owner and v['title']==d['title'] and v['content']==d['versions'][v['version']-1] and v['source_task_id'] is None for v in versions)
            if same:
                result['personal_document'].append(row);result['personal_document_version']+=versions
            else: kept.append('人工变更的原模拟笔记 '+did)
    return result,kept


def predicates(db, plan):
    return {t:' OR '.join('('+ ' AND '.join('`'+k+'`='+sql(r[k]) for k in db.keys(t))+')' for r in rows) or '0=1' for t,rows in plan.items()}


def statement(db, plan, snapshot, *, rollback=False, inject_failure=False):
    predicates_by_table=predicates(db,plan)
    lines=['SET NAMES utf8mb4; SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;',
        'CREATE TEMPORARY TABLE real_import_guard (ok INT NOT NULL CHECK (ok=1));','START TRANSACTION;']
    # Lock complete primary-key ranges so a concurrent request cannot change
    # the deletion or protection set after it has been checked.
    for t in snapshot:
        lines.append('SELECT '+','.join('`'+k+'`' for k in db.keys(t))+f' FROM `{t}` ORDER BY '+','.join('`'+k+'`' for k in db.keys(t))+' FOR UPDATE;')
        expected=sorted(line.split('\t')[-1] for line in snapshot[t])
        # Hash the sorted individual hashes, avoiding GROUP_CONCAT truncation.
        lines.append(f'INSERT INTO real_import_guard VALUES ((SELECT COUNT(*)={len(expected)} FROM `{t}`));')
        if expected:
            lines.append(f'INSERT INTO real_import_guard VALUES ((SELECT COUNT(*)={len(expected)} FROM `{t}` WHERE '+db.fingerprint_expression(t)+' IN ('+','.join(sql(s) for s in expected)+')));')
    for t in ('user_question_mark','practice_record','study_stat','personal_document_version','personal_document','task','school_detail','school','document','question'):
        lines.append(f'DELETE FROM `{t}` WHERE {predicates_by_table[t]};')
    if inject_failure: lines.append('INSERT INTO real_import_guard VALUES (0);')
    for i,q in enumerate(questions(),1):
        values=question_values(q,i);key='source_type='+sql('COURSE_EXERCISE')+' AND source_name='+sql(SOURCE_NAME)+' AND source_question_no='+sql(q['source_question_no'])
        lines.append('INSERT INTO question ('+','.join('`'+k+'`' for k in values)+') SELECT '+','.join(sql(v) for v in values.values())+' WHERE NOT EXISTS (SELECT 1 FROM question WHERE '+key+');')
    for d in documents():
        values=document_values(d)
        lines.append('INSERT INTO document ('+','.join('`'+k+'`' for k in values)+') SELECT '+','.join(sql(v) for v in values.values())+' WHERE NOT EXISTS (SELECT 1 FROM document WHERE title='+sql(d['title'])+' AND source_url='+sql(d['url'])+');')
    for p in schools()['programs']:
        sid='(SELECT id FROM school WHERE name='+sql(p['school'])+')'
        key=f'school_id={sid} AND major_code={sql(p["majorCode"])} AND year=2027 AND major_name={sql(p["major"])}'
        count=int(db.query('SELECT COUNT(*) FROM school_detail WHERE '+key+';'));require(count==1,'真实院校专业自然键缺失或重复，停止导入')
        remark=(f'【官方招生事实】{p["college"]}；'+('学硕' if p['degreeType']=='academic' else '专硕')+'；全日制；初试：'+'、'.join(p['examSubjects'])+f'。{p["note"]} 来源：{p["sourceUrl"]}；定位：{p["locator"]}；核验日期：{p["retrievedAt"]}；版本：{p["version"]}；权限：{p["license"]}')
        # Skip already-current rows: do not bump updated_at on repeated runs.
        lines.append('UPDATE school_detail SET remark='+sql(remark)+' WHERE '+key+' AND NOT (remark <=> '+sql(remark)+');')
    lines.append('ROLLBACK;' if rollback else 'COMMIT;')
    return '\n'.join(lines)+'\n'


def validate_result(db):
    counts={t:int(db.query(f'SELECT COUNT(*) FROM `{t}`;')) for t in ('school','school_detail','question','document')}
    require(counts==dict(school=10,school_detail=15,question=44,document=16),'导入后公共数据数量不符')
    require(db.query("SELECT COUNT(*) FROM question WHERE source_type='COURSE_EXERCISE' AND review_status='APPROVED' AND active=1;")=='44','课程习题发布状态不符')
    for child,parent,fk in (('practice_record','question','question_id'),('user_question_mark','question','question_id'),('school_detail','school','school_id'),('personal_document_version','personal_document','document_id')):
        require(db.query(f'SELECT COUNT(*) FROM `{child}` c LEFT JOIN `{parent}` p ON c.`{fk}`=p.id WHERE p.id IS NULL;')=='0','发现孤立关联：'+child)
    require(db.query("SELECT COUNT(*) FROM school WHERE name LIKE '%测试虚构%';")=='0','虚构院校未清理完')
    return counts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect',action='store_true',help='read-only local DB inspection')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    qs,docs,records=questions(),documents(),corpus()
    preview=dict(target=TARGET,schools=10,programs=15,questions=len(qs),question_subjects=dict(Counter(q['subject'] for q in qs)),documents=dict(Counter(d['subject'] for d in docs)),rag_records=len(records))
    print(json.dumps(preview,ensure_ascii=False),flush=True)
    if not (args.apply or args.inspect):
        print('仅离线预览；未连接数据库。--inspect只读检查，--apply才执行备份及事务替换。');return
    db=Database();plan,kept=deletion_plan(db)
    # Abort on unrelated public additions before any DELETE or backup rehearsal.
    require(int(db.query('SELECT COUNT(*) FROM question;'))==len(plan['question'])+int(db.query('SELECT COUNT(*) FROM question WHERE source_name='+sql(SOURCE_NAME)+';')),'存在未列入计划的公共题目，停止替换')
    require(int(db.query('SELECT COUNT(*) FROM document;'))==len(plan['document'])+int(db.query('SELECT COUNT(*) FROM document WHERE title IN ('+','.join(sql(d['title']) for d in docs)+');')),'存在未列入计划的公共资料，停止替换')
    require(int(db.query('SELECT COUNT(*) FROM school;'))==len(plan['school'])+10 and int(db.query('SELECT COUNT(*) FROM school_detail;'))==len(plan['school_detail'])+15,'存在计划外的院校或专业，停止替换')
    print(json.dumps(dict(delete={t:len(rows) for t,rows in plan.items()},preserved_modified=kept),ensure_ascii=False),flush=True)
    if not args.apply: return
    require(db.values.get('RAG_BACKEND','lexical') in ('lexical','bm25',''),'当前为向量检索配置，需要单独构建对应知识索引，停止自动切换')
    canonical=json.dumps(records,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    release=hashlib.sha256(canonical.encode()).hexdigest()[:16]
    destination=ROOT/'kaoyan-agent/knowledge'/('real-corpus-20261024-'+release+'.json')
    configured=db.values.get('RAG_DATA')
    allowed={ROOT/'kaoyan-agent/knowledge/corpus.json',ROOT/'kaoyan-agent/knowledge/feature-2027-corpus.json',destination}
    require(not configured or Path(configured).resolve() in allowed,'存在自定义RAG_DATA，拒绝覆盖')
    encoded=json.dumps(records,ensure_ascii=False,indent=2)+'\n'
    if destination.exists(): require(destination.read_text()==encoded,'版本化语料路径内容冲突')
    else: destination.write_text(encoded)
    engines=db.query('SELECT DISTINCT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE();')
    require(engines=='InnoDB','存在非事务表，停止导入')
    PRIVATE.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(PRIVATE,0o700)
    with (PRIVATE/'operation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        output=PRIVATE/datetime.now().strftime('%Y%m%d-%H%M%S-%f');output.mkdir(mode=0o700)
        before=db.snapshot();pred=predicates(db,plan)
        dump(output/'plan.json',dict(delete_ids={t:[{k:r[k] for k in db.keys(t)} for r in rows] for t,rows in plan.items()},preserved_modified=kept,new_question_codes=[q['code'] for q in qs],new_document_titles=[d['title'] for d in docs]))
        backup=db.backup(output);write_private(output/'before.env',(ROOT/'.env').read_text())
        require(db.snapshot()==before,'备份期间数据变化；已保留备份，未清理日常库')
        clone_name='kaoyan_realdata_verify_'+secrets.token_hex(6)
        require(db.query('SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='+sql(clone_name)+';',server=True)=='0','独立恢复库名冲突')
        db.query(f'CREATE DATABASE `{clone_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;',server=True)
        clone=Database(clone_name);clone.query(backup.read_text(),timeout=120)
        require(clone.snapshot()==before,'独立恢复结果与备份前指纹不同，未写入日常库')
        dump(output/'restore.json',dict(database=clone_name,all_tables_equal=True,table_counts={t:len(v) for t,v in before.items()}))
        failure_sql=statement(clone,plan,before,inject_failure=True)
        try: clone.query(failure_sql)
        except RuntimeError: pass
        else: raise RuntimeError('失败注入未触发，停止日常导入')
        require(clone.snapshot()==before,'失败事务未完整回滚')
        clone.query(statement(clone,plan,before,rollback=True))
        require(clone.snapshot()==before,'显式回滚验证失败')
        clone.query(statement(clone,plan,before));validate_result(clone)
        repeated_plan,_=deletion_plan(clone);once=clone.snapshot()
        clone.query(statement(clone,repeated_plan,once));require(clone.snapshot()==once,'重复导入改变了已有记录')
        # Recheck immediately before writing; transaction repeats row hashes under locks.
        require(db.snapshot()==before,'预演期间日常数据变化，停止并重新生成清单')
        protected={t:db.fingerprint(t,'NOT ('+pred.get(t,'0=1')+')') for t in before if t!='school_detail'}
        sql_text=statement(db,plan,before);write_private(output/'apply.sql',sql_text)
        db.query(sql_text)
        counts=validate_result(db)
        for t,old_rows in protected.items():
            keys={line.split('\t')[0]:line.split('\t')[1] for line in old_rows}
            now={line.split('\t')[0]:line.split('\t')[1] for line in db.fingerprint(t)}
            require(all(now.get(k)==v for k,v in keys.items()),'无关记录发生改变：'+t)
        # Do not replace user custom corpora; write an immutable release and switch just RAG_DATA.
        set_key(ROOT/'.env','RAG_DATA',str(destination),quote_mode='never')
        report=dict(database=TARGET,counts=counts,deleted={t:len(rows) for t,rows in plan.items()},
            preserved_modified=kept,protected_rows_unchanged=True,restore_database=clone_name,
            backup_restored_and_compared=True,failure_rollback_verified=True,explicit_rollback_verified=True,
            repeated_import_unchanged=True,corpus=str(destination),release_id='rag-v1-'+release,
            services_started=False,model_calls=0,school_recheck_limit='华南师范大学两专业保留2026-10-23核验日期；本次动态详情403')
        dump(output/'report.json',report)
        # Private verification DB remains available for real MySQL HTTP checks.
        print(json.dumps(report,ensure_ascii=False),flush=True)
        print('私密备份与操作报告：'+str(output),flush=True)


if __name__=='__main__':
    try: main()
    except Exception as e:
        print('失败：'+(str(e) if isinstance(e,(ValueError,RuntimeError)) else type(e).__name__),file=sys.stderr)
        sys.exit(1)
