"""Real HTTP/MySQL checks for the dedicated fixture environment only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlencode
import uuid

import httpx
from feature_fixture import ROOT,SUBJECTS,BATCH
from feature_env import Api,BASE,FRONT,PRIVATE,Database,load_config,require,save,sql,start,stop_one


def verify():
    db=Database(load_config());api=Api();checks=[]
    def check(ok,name):
        require(ok,name);checks.append(name)
    creds=json.loads((PRIVATE/'credentials.json').read_text())
    tokens={k:api.login(v) for k,v in creds.items()}
    admin,demo,empty=tokens['admin'],tokens['demo'],tokens['empty']
    fixture=json.loads((ROOT/'scripts/fixtures/feature-2027-schools.json').read_text())
    qs=json.loads((ROOT/'scripts/fixtures/feature-2027-questions.json').read_text())
    qmap={q['code']:q for q in qs}
    def entity(kind,code):
        return db.query(f'SELECT entity_id FROM fixture_item WHERE kind={sql(kind)} AND code={sql(code)};')
    schools=api.call('GET','/api/schools',demo)
    check(len(schools)==10,'10所真实院校可查询')
    for s in fixture['schools']:
        sid=int(entity('school',s['code']))
        detail=api.call('GET',f'/api/schools/{sid}',demo)
        expected=[p for p in fixture['programs'] if p['schoolCode']==s['code']]
        check(len(detail['details'])==len(expected) and all(x['year']==2027 for x in detail['details']),s['code']+'专业数量和年份')
        by_id={x['id']:x for x in detail['details']}
        for p in expected:
            row=by_id[int(entity('program',p['programId']))]
            require(row['majorCode']==p['majorCode'] and row['majorName']==p['major'] and p['college'] in row['remark'] and all(v in row['remark'] for v in p['examSubjects']) and p['sourceUrl'] in row['remark'],'数据库与核验夹具内容不一致')
        check(all(x['enrollmentCount'] is None and x['scoreLine'] is None and 'https://' in x['remark'] for x in detail['details']),s['code']+'未知人数分数为空且保留来源')
    filtered=api.call('GET','/api/schools?'+urlencode(dict(province='北京',level='985',majorName='计算机')),demo)
    check([s['name'] for s in filtered]==['北京航空航天大学'],'院校省份／层次／专业联合筛选')
    check(api.call('GET','/api/schools?'+urlencode(dict(province='不存在的地区')),demo)==[],'院校无匹配为空')
    check(db.query("SELECT COUNT(*) FROM school_detail d LEFT JOIN school s ON d.school_id=s.id WHERE s.id IS NULL;")=='0','专业关联完整')
    corpus=json.loads((PRIVATE/'corpus.json').read_text())
    school_records=[d for d in corpus if d['domain']=='school']
    check(len(school_records)==len(fixture['programs']) and {d['metadata']['programId'] for d in school_records}=={p['programId'] for p in fixture['programs']},'数据库夹具与Agent语料专业编号一致')
    for q in qs:
        qid=int(entity('question',q['code']));stored=api.call('GET',f'/api/questions/admin/{qid}',admin)
        require(stored['reviewStatus']==q['targetStatus'] and stored['active']==q['targetActive'],'题目状态被改变：'+q['code'])
    checks.append('172题管理状态符合160可练习及12审核样例')
    for subject in SUBJECTS.values():
        for difficulty,count in [('EASY',16),('MEDIUM',16),('HARD',8)]:
            selected=api.call('GET','/api/questions/practice?'+urlencode(dict(subject=subject,difficulty=difficulty,limit=100)),demo)
            check(len(selected)==count and all('answer' not in q and 'analysis' not in q for q in selected),subject+'/'+difficulty+'数量与答案隐藏')
            for q in selected:
                detail=api.call('GET',f'/api/questions/{q["id"]}',demo)
                require('answer' not in detail and 'analysis' not in detail,'题目详情泄露答案')
        # Use a known topic present in both conceptual and calculation questions.
        topic=next(q['knowledgePoint'] for q in qs if q['subject']==subject and not q.get('adminExample'))
        selected=api.call('GET','/api/questions/practice?'+urlencode(dict(subject=subject,knowledgePoint=topic,limit=100)),demo)
        check(bool(selected) and all(topic in x['knowledgePoint'] for x in selected),subject+'知识点筛选')
    for prefix in SUBJECTS:
        for n in range(1,4):
            qid=int(entity('question',prefix+'ADMIN'+str(n)))
            api.call('GET',f'/api/questions/{qid}',demo,status=404)
    checks.append('待审／驳回／停用题学生详情不可访问')
    # Restore the designated disabled example to its original disabled state.
    qid=int(entity('question','DSADMIN3'));before=api.call('GET',f'/api/questions/admin/{qid}',admin)
    try:
        api.call('PUT',f'/api/questions/admin/{qid}/active',admin,dict(active=1,version=before['version']))
        api.call('GET',f'/api/questions/{qid}',demo)
        api.call('PUT',f'/api/questions/admin/{qid}/active',admin,dict(active=0,version=before['version']),status=409)
    finally:
        current=api.call('GET',f'/api/questions/admin/{qid}',admin)
        if current['active']!=0:
            api.call('PUT',f'/api/questions/admin/{qid}/active',admin,dict(active=0,version=current['version']))
    checks.append('管理端启停生效、过期版本409且已恢复停用')
    pending=int(entity('question','DSADMIN1'))
    api.call('POST',f'/api/questions/admin/{pending}/review',admin,dict(status='REJECTED',comment='版本冲突检查',version=999),status=409)
    checks.append('过期审核请求409且待审状态保留')
    page=api.call('GET','/api/practice/sessions/page?pageNum=1&pageSize=3',demo)
    last=api.call('GET','/api/practice/sessions/page?pageNum=3&pageSize=3',demo)
    check(page['total']==8 and len(page['list'])==3 and len(last['list'])==2,'8批次分页及末页')
    sessions=[entity('session',f'practice-{n}') for n in range(1,9)]
    total=correct=unanswered=0
    for sid in sessions:
        data=api.call('GET',f'/api/practice/sessions/{sid}/review?pageSize=100',demo)
        for r in data['list']:
            if r.get('isCorrect') is None:
                unanswered+=1;require(r.get('answer') is None and r.get('analysis') is None,'未答答案泄露')
            else:
                total+=1;correct+=r['isCorrect'];require(r['snapshotStatus']=='AVAILABLE' and r.get('answer'),'快照缺失')
    check((total,correct,unanswered)==(30,20,2),'30答／20正确／2未答且历史快照完整')
    stats=api.call('GET','/api/stats/overview',demo)
    check(stats['totalQuestions']==30 and stats['totalCorrect']==20 and abs(stats['accuracy']-2/3)<1e-8,'学习统计与实际提交一致')
    check(stats['totalMinutes'] in (0,None),'未伪造学习时长')
    favorite=api.call('GET','/api/marks/favorite',demo)
    wrong=api.call('GET','/api/marks/wrong',demo)
    check(favorite['total']==6 and wrong['total']>0 and all(x['snapshotStatus']=='AVAILABLE' for x in favorite['list']+wrong['list']),'收藏6题、错题与本人快照可读')
    check(sum(r['wrongCount'] for r in wrong['list'])==10,'错题错误次数合计10次')
    answered=next(x for x in api.call('GET',f'/api/practice/sessions/{sessions[0]}',demo) if x.get('isCorrect') is not None)
    api.call('POST',f'/api/practice/sessions/{sessions[0]}/answer',demo,dict(questionId=answered['questionId'],answer='A'),status=409)
    check(api.call('GET','/api/stats/overview',demo)==stats,'重复提交409且统计不增加')
    api.call('GET','/api/questions/admin/pending',demo,status=403)
    api.call('GET',f'/api/questions/admin/{pending}',demo,status=403)
    checks.append('学生管理请求403')
    for path in ['/api/practice/sessions/page','/api/marks/wrong','/api/marks/favorite','/api/tasks']:
        require(api.call('GET',path,empty)['total']==0,'空账号被污染')
    api.call('GET',f'/api/practice/sessions/{sessions[0]}/review',empty,status=404)
    check(api.call('GET','/api/stats/overview',empty)['totalQuestions']==0,'空账号列表统计为空、跨账号回顾404')
    # Actual recommendation tasks are persisted, with model calls explicitly disabled.
    recommendations=[]
    for pref in [dict(majorCodes=['081200'],degreeType='academic',studyMode='full_time'),
                 dict(majorCodes=['085404'],degreeType='professional',studyMode='full_time',regions=['浙江'],regionConstraint='required'),
                 dict(majorCodes=['081200'],degreeType='academic',regions=['不存在的地区'],regionConstraint='required'),
                 dict(majorCodes=['081200'],degreeType='academic',regions=['河北'],regionConstraint='required')]:
        code='recommend-'+hashlib.sha256(json.dumps(pref,sort_keys=True).encode()).hexdigest()[:12]
        old=entity('task',code)
        if old:
            task=api.call('GET','/api/tasks/'+old,demo)
        else:
            task=api.call('POST','/api/recommends/generate',demo,dict(query='功能验证：按明确条件比较官方来源的专业。',preferences={**pref,'explainWithAi':False}))
            db.query(f"INSERT INTO fixture_item VALUES ('task',{sql(code)},{sql(task['id'])},'done',{sql(code)});")
        require(task['status']=='SUCCESS','推荐任务失败')
        result=task.get('resultPayload')
        if isinstance(result,str): result=json.loads(result)
        require(isinstance(result,dict),'推荐结果缺失')
        recommendations.append((task,result))
        require(len(result['candidates'])<=5,'推荐超过5候选')
        require(all(c['year']==2027 and c['majorCode'] in pref['majorCodes'] and c['degreeType']==pref['degreeType'] for c in result['candidates']),'推荐硬条件失效')
        require(all(c['sourceIds'] for c in result['candidates']) and all(r['url'].startswith('https://') for r in result['references']),'推荐引用缺失')
    check(len(recommendations[0][1]['candidates'])==5,'超过5个匹配项目时仅返回5个候选')
    check([c['school'] for c in recommendations[1][1]['candidates']]==['浙江科技大学'],'浙江085404硬筛选及引用')
    check(recommendations[2][1]['outcome']=='UNSUPPORTED' and recommendations[2][1]['candidates']==[],'推荐无匹配不放宽条件')
    ysu=recommendations[3][1]
    check([c['school'] for c in ysu['candidates']]==['燕山大学'] and ysu['references'][0]['url'].startswith('https://yz.chsi.com.cn/zsml/yjfxdetail'), '燕山大学补充官方学习方式证据实际用于推荐')
    api.call('GET','/api/tasks/'+recommendations[0][0]['id'],empty,status=404)
    checks.append('推荐任务持久化且跨账号404')
    # A failed multi-statement transaction must leave no fixture row behind.
    probe='rollback-'+str(uuid.uuid4())
    try:
        db.query(f"START TRANSACTION;INSERT INTO fixture_item VALUES ('probe',{sql(probe)},'none','test','none');"
                 f"INSERT INTO fixture_item VALUES ('probe',{sql(probe)},'duplicate','test','none');COMMIT;")
        raise AssertionError('Expected duplicate-key error')
    except RuntimeError:
        require(entity('probe',probe)=='','失败事务残留记录')
    checks.append('真实MySQL失败事务回滚，无残留记录')
    # Repeat seeding, checking every business table's checksum before and after.
    table_names=['user','school','school_detail','question','document','practice_record','user_question_mark','study_stat','task']
    before=db.query('CHECKSUM TABLE '+','.join('`'+t+'`' for t in table_names)+';')
    # main CLI already holds the operation lock; invoke seed in-process to avoid a nested lock.
    import importlib.util
    spec=importlib.util.spec_from_file_location('feature_test_cli',ROOT/'scripts/feature-test.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.seed()
    check(db.query('CHECKSUM TABLE '+','.join('`'+t+'`' for t in table_names)+';')==before,'重复导入所有业务表校验值不变')
    stop_one('backend');start()
    token=api.login(creds['demo'])
    check(api.call('GET','/api/stats/overview',token)==stats and api.call('GET','/api/practice/sessions/page',token)['total']==8,'真实Java重启后账号、作答和统计恢复')
    health=httpx.get('http://127.0.0.1:18001/health',trust_env=False).json()
    require(not health.get('modelEnabled'), '模型不应启用')
    checks.append('Agent真实服务模型关闭')
    path=PRIVATE/('http-report-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
    save(path,dict(checks=checks,passed=len(checks),statistics=stats,wrongQuestions=wrong['total'],
        sourcePrograms=len(school_records),paidModelCalls=0,browser='not run by this script',
        limitations=['草稿、提示、正式结束批次等未实现能力不在本次通过范围','390像素浏览器宽度不代表真实手机']))
    print(f'真实HTTP/MySQL验证通过{len(checks)}项；报告：{path}',flush=True)
