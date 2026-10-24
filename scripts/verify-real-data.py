"""Real MySQL/Redis/Java/Agent verification in the owned restored DB only.

Starts random-port temporary processes and stops only those processes. All
practice actions belong to two new verification students in the restored DB.
Never calls a paid model, modifies daily accounts, or reads browser profiles.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import urlencode

import httpx

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('real_import',ROOT/'scripts/import-real-data.py')
imp=importlib.util.module_from_spec(spec);spec.loader.exec_module(imp)


def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));return s.getsockname()[1]


def stop(p):
    if p is not None and p.poll() is None:
        p.terminate()
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--browser',action='store_true')
    args=parser.parse_args();run=args.run.resolve()
    imp.require(run.parent==imp.PRIVATE and (run/'restore.json').is_file(),'必须使用本轮生成的私密恢复验证目录')
    info=json.loads((run/'report.json').read_text());db=imp.Database(info['restore_database'])
    imp.require(json.loads((run/'restore.json').read_text())['database']==db.name,'恢复库身份不符')
    output=run/('http-'+secrets.token_hex(4));output.mkdir(mode=0o700)
    java_port,agent_port,redis_port,front_port=port(),port(),port(),port()
    base=f'http://127.0.0.1:{java_port}';agent_base=f'http://127.0.0.1:{agent_port}'
    env=os.environ.copy()
    redis_password=secrets.token_urlsafe(24)
    env.update(AGENT_INTERNAL_KEY=secrets.token_hex(32),JWT_SECRET=secrets.token_hex(32),AGENT_BASE_URL=agent_base,
        SPRING_PROFILES_ACTIVE='realdata-verify',SPRING_DATASOURCE_DRIVER_CLASS_NAME='com.mysql.cj.jdbc.Driver',
        SPRING_DATASOURCE_URL=f'jdbc:mysql://127.0.0.1:{db.values.get("DB_PORT") or "3306"}/{db.name}?serverTimezone=Asia/Shanghai&useUnicode=true&characterEncoding=utf-8&useSSL=false&allowPublicKeyRetrieval=true',
        SPRING_DATASOURCE_USERNAME=db.values.get('DB_USER') or '',SPRING_DATASOURCE_PASSWORD=db.values.get('DB_PASSWORD') or '',
        SPRING_DATA_REDIS_HOST='127.0.0.1',SPRING_DATA_REDIS_PORT=str(redis_port),SPRING_DATA_REDIS_PASSWORD=redis_password,
        REDIS_PASSWORD=redis_password,LLM_ENABLED='false',LLM_API_KEY='',LLM_BASE_URL='https://example.invalid',
        RAG_DATA=info['corpus'],RAG_BACKEND='lexical',QDRANT_URL='',QDRANT_API_KEY='',
        QUESTION_INDEX=str(output/'questions'),API_PROXY_TARGET=base,
        NODE_PATH=str(ROOT/'kaoyan-frontend/node_modules'))
    processes=[];logs=[];checks=[];credentials=[]
    def launch(command,cwd,name):
        path=output/(name+'.log');fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        log=os.fdopen(fd,'w');logs.append(log)
        p=subprocess.Popen(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(p);return p
    client=httpx.Client(timeout=30,trust_env=False)
    def ready(p,url,status=200):
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            imp.require(p.poll() is None,'临时服务退出，检查私密服务日志')
            try:
                if client.get(url).status_code==status:return
            except httpx.HTTPError:pass
            time.sleep(.2)
        raise RuntimeError('临时服务启动超时')
    def check(name,condition):
        checks.append(dict(name=name,passed=bool(condition)))
        imp.require(condition,name)
    def api(method,path,token=None,body=None,status=200):
        r=client.request(method,base+path,headers={'Authorization':'Bearer '+token} if token else {},json=body)
        imp.require(r.status_code==status,f'{method} {path.split("?")[0]} 状态{r.status_code}，预期{status}')
        if status!=200:return None
        envelope=r.json();imp.require(envelope['code']==0,'业务返回失败：'+path.split('?')[0]);return envelope['data']
    try:
        config=output/'redis.conf'
        imp.write_private(config,f'bind 127.0.0.1\nport {redis_port}\nsave ""\nappendonly no\nrequirepass {redis_password}\n')
        redis=launch([shutil.which('redis-server'),str(config)],output,'redis')
        agent=launch([sys.executable,'-m','uvicorn','main:create_app','--factory','--host','127.0.0.1','--port',str(agent_port)],ROOT/'kaoyan-agent','agent')
        ready(agent,agent_base+'/health')
        health=client.get(agent_base+'/health').json()
        check('Agent加载本轮31条真实语料且关闭付费模型',health['releaseId']==info['release_id'] and health['modelEnabled'] is False)
        java=launch(['java','-jar',str(ROOT/'kaoyan-B/target/kaoyan-backend-1.0.0.jar'),'--server.address=127.0.0.1',f'--server.port={java_port}'],ROOT/'kaoyan-B','java')
        ready(java,base+'/api/tasks',401)
        print('独立恢复库的临时Java、Redis、Agent已启动，开始实际HTTP核验。',flush=True)
        for suffix in ('reader','other'):
            c=dict(username='realverify_'+secrets.token_hex(5)+'_'+suffix,password=secrets.token_urlsafe(18))
            api('POST','/api/auth/register',body=c)
            c['token']=api('POST','/api/auth/login',body=c)['accessToken'];credentials.append(c)
        token,other=[c['token'] for c in credentials]
        schools=api('GET','/api/schools',token)
        check('10校可浏览且无虚构校名',len(schools)==10 and all('虚构' not in s['name'] for s in schools))
        filtered=api('GET','/api/schools?'+urlencode(dict(province='北京',level='985',majorName='计算机')),token)
        check('真实MySQL院校联合筛选',[s['name'] for s in filtered]==['北京航空航天大学'])
        all_details=[d for s in schools for d in api('GET',f'/api/schools/{s["id"]}',token)['details']]
        check('15专业年份来源及未知数值',len(all_details)==15 and all(d['year']==2027 and 'https://' in d['remark'] and d['enrollmentCount'] is None and d['scoreLine'] is None for d in all_details))
        docs=api('GET','/api/documents',token)
        check('四科各4份已发布真实来源资料',len(docs)==16 and all(sum(d['subject']==s for d in docs)==4 for s in ('数据结构','操作系统','计算机组成原理','计算机网络')))
        selected=api('GET','/api/questions/practice?'+urlencode(dict(subject='数据结构',limit=100)),token)
        check('44课程题学生列表不泄露答案',len(selected)==44 and all('answer' not in q and 'analysis' not in q for q in selected))
        for s in ('操作系统','计算机组成原理','计算机网络'):
            check(s+'缺题如实返回空列表',api('GET','/api/questions/practice?'+urlencode(dict(subject=s,limit=100)),token)==[])
        qid=selected[0]['id'];q=api('GET',f'/api/questions/{qid}',token)
        check('单题提交前答案隐藏','answer' not in q and 'analysis' not in q)
        api('GET',f'/api/questions/admin/{qid}',token,status=403)
        check('学生不能访问管理题目来源与答案',True)
        session=api('POST','/api/practice/sessions',token,dict(subject='数据结构',count=2,source='NORMAL'))['sessionId']
        rows=api('GET',f'/api/practice/sessions/{session}',token)
        check('新批次固定2道真实题目',len(rows)==2)
        api('GET',f'/api/practice/sessions/{session}',other,status=404)
        check('批次跨账号返回404',True)
        review=api('GET',f'/api/practice/sessions/{session}/review',token)
        check('未提交批次回顾隐藏答案',all(r.get('answer') is None and r.get('analysis') is None for r in review['list']))
        answer_map={int(r['id']):r['answer'] for r in db.records('question')}
        q1,q2=[r['questionId'] for r in rows]
        correct=api('POST',f'/api/practice/sessions/{session}/answer',token,dict(questionId=q1,answer=answer_map[q1]))
        wrong_answer=next(c for c in 'ABCD' if c!=answer_map[q2])
        wrong=api('POST',f'/api/practice/sessions/{session}/answer',token,dict(questionId=q2,answer=wrong_answer))
        check('Java确定性判分和解析',correct['isCorrect']==1 and wrong['isCorrect']==0 and wrong['answer']==answer_map[q2] and bool(wrong['analysis']))
        api('POST',f'/api/practice/sessions/{session}/answer',token,dict(questionId=q1,answer=answer_map[q1]),status=409)
        check('重复提交409且不重复计数',api('GET','/api/stats/overview',token)['totalQuestions']==2)
        api('POST',f'/api/marks/favorite/{q2}',token)
        check('错题与收藏和判分一致',api('GET','/api/marks/wrong',token)['total']==1 and api('GET','/api/marks/favorite',token)['total']==1)
        check('另一账号无错题收藏',api('GET','/api/marks/wrong',other)['total']==0 and api('GET','/api/marks/favorite',other)['total']==0)
        overview=api('GET','/api/stats/overview',token)
        check('统计2答1对且未伪造学习时长',overview['totalQuestions']==2 and overview['totalCorrect']==1 and overview['totalMinutes'] is None and overview['accuracy']==.5)
        task=api('POST','/api/tasks',token,dict(taskType='KNOWLEDGE_QA',input={'query':'TCP的流量控制和拥塞控制有什么区别？'}))
        result=task.get('resultPayload') or {}
        check('Java到真实Agent离线检索引用本轮资料',task['status']=='SUCCESS' and task['releaseId']==info['release_id'] and bool(result.get('references')) and all(r['id'].startswith('real-knowledge-') for r in result['references']))
        api('GET','/api/tasks/'+task['id'],other,status=404)
        check('检索任务跨账号隔离',True)
        # The local embedding uses existing public weights only, in a fresh store.
        public=[{k:r.get(v) for k,v in [('id','id'),('version','version'),('subject','subject'),('difficulty','difficulty'),('knowledgePoint','knowledge_point'),('content','content'),('optionA','option_a'),('optionB','option_b'),('optionC','option_c'),('optionD','option_d')]} for r in db.records('question')]
        headers={'X-Internal-Key':env['AGENT_INTERNAL_KEY']}
        indexed=client.post(agent_base+'/internal/rag/questions/index',headers=headers,json={'questions':public});indexed.raise_for_status();release=indexed.json()['releaseId']
        deadline=time.monotonic()+120
        while True:
            state=client.get(agent_base+'/internal/rag/questions/index/'+release,headers=headers).json()['status']
            if state!='BUILDING':break
            imp.require(time.monotonic()<deadline,'本地题目索引超时');time.sleep(.2)
        check('44题真实本地Embedding与Qdrant建索引',state=='READY')
        search=client.post(agent_base+'/internal/rag/questions/search',headers=headers,json={'releaseId':release,'query':'栈','allowedIds':[q['id'] for q in public]});search.raise_for_status()
        check('题目检索只返回当前允许ID',bool(search.json()['matches']) and all(m['id'] in answer_map for m in search.json()['matches']))
        if args.browser:
            front=launch(['node','node_modules/vite/bin/vite.js','preview','--host','127.0.0.1','--port',str(front_port),'--strictPort'],ROOT/'kaoyan-frontend','frontend')
            front_base=f'http://127.0.0.1:{front_port}';ready(front,front_base)
            creds_file=output/'browser-credentials.json';imp.dump(creds_file,{k:credentials[0][k] for k in ('username','password')})
            browser=subprocess.run(['node',str(ROOT/'scripts/browser-real-data.cjs'),front_base,str(creds_file),str(output)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=90)
            imp.write_private(output/'browser-run.log',browser.stdout+'\n'+browser.stderr)
            check('桌面与390宽度真实后端页面',browser.returncode==0)
        # Restart only this temporary Java and verify actual persisted records.
        stop(java)
        java=launch(['java','-jar',str(ROOT/'kaoyan-B/target/kaoyan-backend-1.0.0.jar'),'--server.address=127.0.0.1',f'--server.port={java_port}'],ROOT/'kaoyan-B','java-restart')
        ready(java,base+'/api/tasks',401)
        check('Java重启后练习与收藏持久保存',api('GET',f'/api/practice/sessions/{session}',token)[0]['userAnswer'] is not None and api('GET','/api/marks/favorite',token)['total']==1)
        report=dict(scope='owned restored MySQL DB; real Redis/Java/FastAPI/local FastEmbed/Qdrant; model disabled',database=db.name,checks=checks,paid_model_calls=0,daily_database_written=False,question_index_release=release)
        imp.dump(output/'verification.json',report)
        print(json.dumps(dict(checks=len(checks),passed=True,report=str(output/'verification.json')),ensure_ascii=False),flush=True)
    except Exception as error:
        imp.dump(output/'failure.json',dict(checks=checks,error=type(error).__name__,message=str(error) if isinstance(error,RuntimeError) else '诊断见私密日志'))
        raise
    finally:
        for p in reversed(processes):stop(p)
        for f in logs:f.close()
        client.close()


if __name__=='__main__':
    try:main()
    except Exception as e:
        print('验证失败：'+(str(e) if isinstance(e,RuntimeError) else type(e).__name__),file=sys.stderr);sys.exit(1)
