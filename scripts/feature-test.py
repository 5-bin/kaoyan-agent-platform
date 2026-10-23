"""Preview or prepare an isolated, usable MySQL/Redis/Java/Python/Vue fixture environment."""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlencode
import uuid

from feature_fixture import BATCH, ROOT, SUBJECTS, validate_questions
from feature_env import (Api,BASE,FRONT,PRIVATE,Database,load_config,prepare,require,
                         runtime_env,save,sql,start,stop_one,owned,process_state)


def fixtures():
    questions=json.loads((ROOT/'scripts/fixtures/feature-2027-questions.json').read_text())
    schools=json.loads((ROOT/'scripts/fixtures/feature-2027-schools.json').read_text())
    validate_questions(questions)
    require(len(schools['schools'])==10,'应有10所院校')
    codes={s['code'] for s in schools['schools']}
    require(len(codes)==10,'院校编号重复')
    require({p['schoolCode'] for p in schools['programs']}==codes,'每校至少一个专业')
    require(len({p['programId'] for p in schools['programs']})==len(schools['programs']),'专业编号重复')
    for p in schools['programs']:
        require(p['reviewStatus']=='verified' and p['year']==2027,'存在未核验或非2027专业')
        require(len(p['examSubjects'])==4 and all(len(v)==3 and v.isdigit() for v in p['examSubjects']),'科目不完整')
        require(p['sourceUrl'].startswith('https://') and p['locator'] and p['license'],'来源不完整')
        require(p['enrollmentCount'] is None and p['scoreLine'] is None,'不导入未核验人数或分数线')
    return questions,schools


def checksum(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def make_corpus(schools):
    # Preserve the existing same-project knowledge summaries and their original dates.
    existing=json.loads((ROOT/'kaoyan-agent/knowledge/corpus.json').read_text())
    records=[x for x in existing if x['domain']=='knowledge']
    for p in schools['programs']:
        keys=['programId','school','college','major','majorCode','year','degreeType','region','studyMode','examSubjects']
        metadata={k:p[k] for k in keys};metadata['updatedAt']=p['retrievedAt']
        content=(f'{p["school"]}{p["college"]}2027年全日制{p["major"]}（{p["majorCode"]}），'
            f'{"学术学位" if p["degreeType"]=="academic" else "专业学位"}，初试代码为'+
            '、'.join(p['examSubjects'])+'。'+p['note']+'未收录招生人数、分数线或录取概率。')
        records.append(dict(id=p['programId'],domain='school',title=f'{p["school"]}2027年{p["major"]}核验摘要',
            url=p['sourceUrl'],locator=p['locator'],version=p['version'],retrievedAt=p['retrievedAt'],
            license=p['license'],reviewStatus='verified',content=content,metadata=metadata,keywords=[p['school'],p['majorCode']]))
    PRIVATE.mkdir(parents=True,mode=0o700,exist_ok=True)
    path=PRIVATE/'corpus.json'
    if path.exists():
        require(json.loads(path.read_text())==records,'专用语料已改变，拒绝静默覆盖；请先核对来源与当前运行版本')
    else: save(path,records)
    return records


def item(db,kind,code):
    rows=db.rows(f'SELECT JSON_OBJECT(\'id\',entity_id,\'state\',state,\'checksum\',checksum) FROM fixture_item WHERE kind={sql(kind)} AND code={sql(code)};')
    return rows[0] if rows else None


def put_item(db,kind,code,entity_id,state,value):
    db.query(f'INSERT INTO fixture_item VALUES ({sql(kind)},{sql(code)},{sql(entity_id)},{sql(state)},{sql(checksum(value))}) '
             'ON DUPLICATE KEY UPDATE state=VALUES(state);')


def accounts(db,api):
    credentials=json.loads((PRIVATE/'credentials.json').read_text());tokens={}
    for key,credential in credentials.items():
        username=credential['username']
        rows=db.rows('SELECT JSON_OBJECT(\'id\',id,\'role\',role) FROM user WHERE username='+sql(username)+';')
        created=not rows
        if created:
            api.call('POST','/api/auth/register',body=credential)
            rows=db.rows('SELECT JSON_OBJECT(\'id\',id,\'role\',role) FROM user WHERE username='+sql(username)+';')
        require(len(rows)==1,'账号异常')
        uid=rows[0]['id']
        # Authenticate the generated credential before considering any bootstrap change.
        api.login(credential)
        old=item(db,'account',key)
        if created: put_item(db,'account',key,uid,'created',{'username':username})
        # The only role elevation in this task is for the generated admin of the fixed isolated DB.
        if key=='admin' and rows[0]['role']=='STUDENT':
            require(created or (old and old['state']=='created'),'管理员角色已改变，拒绝重新提权')
            require(db.query('SELECT COUNT(*) FROM practice_record WHERE user_id='+str(uid)+';')=='0','管理账号已有练习，拒绝提权')
            db.query(f"UPDATE user SET role='ADMIN' WHERE id={uid} AND username={sql(username)} AND role='STUDENT';")
        tokens[key]=api.login(credential)
        expected='ADMIN' if key=='admin' else 'STUDENT'
        require(api.call('GET','/api/users/me',tokens[key])['role']==expected,'账号角色不符')
        put_item(db,'account',key,uid,'done',{'username':username})
        if key!='admin' and not item(db,'profile',key):
            api.call('PUT','/api/users/profile',tokens[key],dict(targetMajor='081200',examYear=2027,
                background='【独立功能测试账号】本账号供接口与页面验证，不代表真实考生。'))
            put_item(db,'profile',key,uid,'done',{'year':2027})
    return tokens


def seed_schools(db,schools):
    for s in schools['schools']:
        old=item(db,'school',s['code'])
        if old:
            require(old['checksum']==checksum(s),'院校夹具内容改变，停止以免覆盖人工修改')
            continue
        require(db.query(f'SELECT COUNT(*) FROM school WHERE name={sql(s["name"])};')=='0','院校同名冲突')
        statement=f'INSERT INTO school (name,province,level) VALUES ({sql(s["name"])},{sql(s["province"])},{sql(s["level"])});'
        db.query('START TRANSACTION;'+statement+
            f"INSERT INTO fixture_item VALUES ('school',{sql(s['code'])},LAST_INSERT_ID(),'done',{sql(checksum(s))});COMMIT;")
    for p in schools['programs']:
        old=item(db,'program',p['programId'])
        if old:
            require(old['checksum']==checksum(p),'专业夹具内容改变，停止以免覆盖人工修改')
            continue
        school_id=int(item(db,'school',p['schoolCode'])['id'])
        remark=f'【2027官方来源核验摘要】{p["college"]}；'+('学硕' if p['degreeType']=='academic' else '专硕')+'；全日制；初试：'+'、'.join(p['examSubjects'])+f'。{p["note"]} 来源：{p["sourceUrl"]}；定位：{p["locator"]}；核验：{p["retrievedAt"]}；版本：{p["version"]}；权限：{p["license"]}'
        db.query('START TRANSACTION;INSERT INTO school_detail (school_id,major_name,major_code,year,enrollment_count,score_line,remark) '
            f'VALUES ({school_id},{sql(p["major"])},{sql(p["majorCode"])},2027,NULL,NULL,{sql(remark)});'
            f"INSERT INTO fixture_item VALUES ('program',{sql(p['programId'])},LAST_INSERT_ID(),'done',{sql(checksum(p))});COMMIT;")


def seed_questions(db,api,token,questions):
    fields=('subject','knowledgePoint','difficulty','content','answer','analysis','sourceType','sourceName','sourceLocator','permissionNote')
    added=0
    for q in questions:
        old=item(db,'question',q['code'])
        if old and old['state']=='done':
            require(old['checksum']==checksum(q),'题库夹具内容改变，拒绝覆盖已存在题目')
            continue
        rows=db.rows('SELECT JSON_OBJECT(\'id\',id) FROM question WHERE source_name='+sql(BATCH)+' AND source_locator='+sql(q['sourceLocator'])+';')
        if not rows:
            payload={k:q[k] for k in fields};payload.update(dict(zip(['optionA','optionB','optionC','optionD'],q['options'])))
            created=api.call('POST','/api/questions/admin',token,payload);qid=created['id'];added+=1
            put_item(db,'question',q['code'],qid,'created',q)
        else:
            require(len(rows)==1,'题目来源重复')
            qid=rows[0]['id']
            require(old and old['state']=='created','存在未登记题目，拒绝接管')
        current=api.call('GET',f'/api/questions/admin/{qid}',token)
        require(current['content']==q['content'] and current['version']==1 and current['reviewStatus']=='PENDING_REVIEW',
                '中断期间题目已变化，保留人工修改并停止自动审核')
        if q['targetStatus']!='PENDING_REVIEW':
            api.call('POST',f'/api/questions/admin/{qid}/review',token,dict(status=q['targetStatus'],version=1,
                comment='自动化功能测试：原创夹具已做结构校验与计算复核；仅独立测试库使用，不代表人工审核。'))
        if q['targetActive']==0:
            current=api.call('GET',f'/api/questions/admin/{qid}',token)
            api.call('PUT',f'/api/questions/admin/{qid}/active',token,dict(active=0,version=current['version']))
        put_item(db,'question',q['code'],qid,'done',q)
    print(f'题库就绪：本次新增{added}题，已有记录未覆盖。',flush=True)


def seed_documents(db,api,token):
    records=json.loads((PRIVATE/'corpus.json').read_text())
    for d in [x for x in records if x['domain']=='knowledge']:
        if item(db,'document',d['id']): continue
        body=dict(title='【功能测试资料】'+d['title'],subject=d['subject'],sourceUrl=d['url'],
            content=d['content']+f'\n\n来源：{d["url"]}\n定位：{d["locator"]}\n原摘要版本：{d["version"]}；原核验日期：{d["retrievedAt"]}\n{d["license"]}\n此处为同项目已有短摘要的功能测试副本，本次未声称重新完成知识资料内容审核。')
        created=api.call('POST','/api/documents/admin',token,body)
        api.call('POST',f'/api/documents/admin/{created["id"]}/review',token,dict(status='PUBLISHED',comment='自动化测试发布：仅用于独立测试库资料浏览，不代表新增人工审核。'))
        put_item(db,'document',d['id'],created['id'],'done',body)


def seed_sessions(db,api,token,questions):
    mapping={int(item(db,'question',q['code'])['id']):q for q in questions}
    favorites=[];completed=0
    for n in range(8):
        code=f'practice-{n+1}'
        previous=item(db,'session',code)
        if previous:
            sid=previous['id']
        else:
            subject=list(SUBJECTS.values())[n%4]
            sid=api.call('POST','/api/practice/sessions',token,dict(subject=subject,count=4))['sessionId']
            put_item(db,'session',code,sid,'created',{'subject':subject,'count':4})
        records=api.call('GET',f'/api/practice/sessions/{sid}',token)
        require(len(records)==4,'批次题数已改变，不补造历史')
        for order,r in enumerate(records):
            pos=n*4+order
            if n==7 and order>=2: continue
            q=mapping[r['questionId']]
            if len(favorites)<6 and r['questionId'] not in favorites: favorites.append(r['questionId'])
            answer=q['answer'] if pos<20 else 'ABCD'[('ABCD'.index(q['answer'])+1)%4]
            if r.get('isCorrect') is None:
                result=api.call('POST',f'/api/practice/sessions/{sid}/answer',token,dict(questionId=r['questionId'],answer=answer))
                require(result['isCorrect']==int(pos<20),'判分与预期不一致')
            completed+=1
        put_item(db,'session',code,sid,'done',{'count':4})
    require(len(favorites)==6,'收藏题目不足6个')
    for qid in favorites:
        if not item(db,'favorite',str(qid)):
            api.call('POST',f'/api/marks/favorite/{qid}',token)
            put_item(db,'favorite',str(qid),qid,'done',{})
    require(completed==30,'预期30次作答')
    print('通过真实接口准备8批次、30次提交和6个收藏。',flush=True)


def seed():
    questions,schools=fixtures();db=Database(load_config());db.backup();api=Api()
    tokens=accounts(db,api)
    seed_schools(db,schools)
    seed_questions(db,api,tokens['admin'],questions)
    seed_documents(db,api,tokens['admin'])
    seed_sessions(db,api,tokens['demo'],questions)
    save(PRIVATE/'seed-report.json',dict(batch=BATCH,schoolCount=10,programCount=len(schools['programs']),
        playableQuestions=160,adminExamples=12,sessions=8,answered=30,correct=20,unanswered=2,
        apiGenerated=True,paidModelCalls=0,credentialsFile=str(PRIVATE/'credentials.json')))


def build():
    env=runtime_env()
    # Existing chain tests deliberately assert the default small corpus, not the new demo corpus.
    env['RAG_DATA']=str(ROOT/'kaoyan-agent/knowledge/corpus.json')
    log=PRIVATE/'build.log'
    with open(log,'ab') as out:
        os.chmod(log,0o600)
        for command,cwd in [(['bash','mvnw','-B','-ntp','package'],ROOT/'kaoyan-B'),(['npm','run','build'],ROOT/'kaoyan-frontend')]:
            print('构建并检查：'+str(cwd.name),flush=True)
            result=subprocess.run(command,cwd=cwd,env=env,stdout=out,stderr=subprocess.STDOUT)
            require(result.returncode==0,'构建或测试失败；见本机私密build.log')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',nargs='?',default='preview',choices=['preview','prepare','build','start','seed','verify','status','stop','all'])
    parser.add_argument('--apply',action='store_true',help='明确执行独立库写入及服务启动')
    args=parser.parse_args()
    questions,schools=fixtures()
    print(f'夹具校验通过：10校、{len(schools["programs"])}专业、160练习题、12审核样例。',flush=True)
    if args.command=='preview':
        print('仅预览，未连接数据库、未启动服务。');return
    if args.command=='status':
        states=process_state()
        for name in ('redis','agent','backend','frontend'):
            print(name+('：本环境进程运行中' if owned(states.get(name)) else '：未登记运行进程'))
        return
    require(args.apply,'执行需 --apply；默认不会连接数据库或启动服务')
    PRIVATE.mkdir(parents=True,mode=0o700,exist_ok=True)
    with open(PRIVATE/'operation.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.command=='stop':
            for name in ('frontend','backend','agent','redis'):
                if owned(process_state().get(name)): stop_one(name)
            print('仅停止本独立环境进程，数据库及Redis数据保留。')
        if args.command in ('prepare','all'): make_corpus(schools);prepare()
        if args.command in ('build','all'): build()
        if args.command in ('start','all'): start()
        if args.command in ('seed','all'): seed()
        if args.command in ('verify','all'):
            from verify_feature_env import verify
            verify()


if __name__=='__main__':
    try: main()
    except Exception as error:
        print('失败：'+(str(error) if isinstance(error,RuntimeError) else type(error).__name__),file=sys.stderr)
        sys.exit(1)
