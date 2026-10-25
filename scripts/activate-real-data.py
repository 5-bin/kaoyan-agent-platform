"""Explicitly authorized daily service activation, preview by default.

Starts the existing Homebrew Redis configuration (preserving its data folder),
restarts only the verified Java/Agent listeners of this project, and warms the
current public question index without using the paid LLM.
"""
import argparse
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import sys
import time

import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('real_import',ROOT/'scripts/import-real-data.py')
imp=importlib.util.module_from_spec(spec);spec.loader.exec_module(imp)


def listener(port):
    p=subprocess.run(['lsof','-nP','-iTCP:'+str(port),'-sTCP:LISTEN','-t'],capture_output=True,text=True)
    ids=set(p.stdout.split());imp.require(len(ids)<=1,'目标端口存在多个监听进程，停止操作')
    return int(next(iter(ids))) if ids else None


def owned(pid, folder, executable):
    p=subprocess.run(['lsof','-a','-p',str(pid),'-d','cwd','-Fn'],capture_output=True,text=True)
    cwd=next((x[1:] for x in p.stdout.splitlines() if x.startswith('n')),None)
    comm=subprocess.run(['ps','-p',str(pid),'-o','comm='],capture_output=True,text=True).stdout.strip()
    return cwd==str(folder) and Path(comm).name.lower().startswith(executable)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if not args.apply:
        print('预览：本机6379 Redis，重启本项目8080 Java与8001 Agent；--apply才启停。');return
    values=dotenv_values(ROOT/'.env');imp.require(values.get('DB_NAME')=='kaoyan_dev','日常数据库配置不符')
    imp.require(values.get('REDIS_HOST') in (None,'','127.0.0.1','localhost') and values.get('REDIS_PORT') in (None,'','6379'),'本次仅授权本机6379 Redis')
    current={8001:listener(8001),8080:listener(8080)}
    for port,pid in current.items():
        if pid:imp.require(owned(pid,ROOT/('kaoyan-agent' if port==8001 else 'kaoyan-B'),'python' if port==8001 else 'java'),'监听进程不属于本项目，拒绝停止')
    runtime=ROOT/'.cache/local-runtime'/datetime.now().strftime('%Y%m%d-%H%M%S');runtime.mkdir(parents=True,mode=0o700)
    env=os.environ.copy();env.update({k:str(v) for k,v in values.items() if v is not None})
    client=httpx.Client(timeout=8,trust_env=False)
    children=[]
    def launch(command,cwd,name):
        fd=os.open(runtime/(name+'.log'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as out:
            p=subprocess.Popen(command,cwd=cwd,env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
        children.append(p);return p
    redis_pid=listener(6379)
    if not redis_pid:
        config=Path('/opt/homebrew/etc/redis.conf');imp.require(config.is_file(),'缺少现有Redis配置，不创建替代数据目录')
        options={}
        for line in config.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                parts=shlex.split(line,comments=True)
                if len(parts)>=2: options[parts[0]]=parts[1:]
        configured=(options.get('requirepass') or [''])[0]
        imp.require(configured==(values.get('REDIS_PASSWORD') or ''),'Redis现有密码与项目配置不一致，拒绝改密')
        redis=launch(['/opt/homebrew/bin/redis-server',str(config),'--bind','127.0.0.1','--port','6379','--daemonize','no'],ROOT,'redis')
        redis_pid=redis.pid
    redis_env=env.copy();redis_env['REDISCLI_AUTH']=values.get('REDIS_PASSWORD') or ''
    for _ in range(50):
        p=subprocess.run(['/opt/homebrew/bin/redis-cli','-h','127.0.0.1','-p','6379','ping'],capture_output=True,text=True,env=redis_env)
        if p.returncode==0 and p.stdout.strip()=='PONG':break
        time.sleep(.1)
    else:raise RuntimeError('日常Redis启动或认证失败；未停止原Java和Agent')
    print('日常Redis已就绪，沿用现有配置与持久数据路径。',flush=True)
    for port,pid in current.items():
        if pid:
            os.kill(pid,signal.SIGTERM)
            deadline=time.monotonic()+20
            while listener(port)==pid and time.monotonic()<deadline:time.sleep(.2)
            imp.require(listener(port) is None,'原服务未正常退出，拒绝强制停止')
    agent=launch([sys.executable,'-m','uvicorn','main:create_app','--factory','--host','127.0.0.1','--port','8001'],ROOT/'kaoyan-agent','agent')
    java=launch(['java','-jar','target/kaoyan-backend-1.0.0.jar','--server.address=127.0.0.1','--server.port=8080'],ROOT/'kaoyan-B','java')
    health=None
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        imp.require(agent.poll() is None and java.poll() is None,'新服务退出，请检查本次私密日志')
        try:
            r=client.get('http://127.0.0.1:8001/health');j=client.get('http://127.0.0.1:8080/api/tasks')
            if r.status_code==200 and j.status_code==401:health=r.json();break
        except httpx.HTTPError:pass
        time.sleep(.25)
    imp.require(health is not None,'服务健康检查超时')
    db=imp.Database();imp.validate_result(db)
    records=db.records('question',"review_status='APPROVED' AND active=1")
    public=[dict(id=r['id'],version=r['version'],subject=r['subject'],difficulty=r['difficulty'],knowledgePoint=r['knowledge_point'],content=r['content'],optionA=r['option_a'],optionB=r['option_b'],optionC=r['option_c'],optionD=r['option_d']) for r in records]
    headers={'X-Internal-Key':values['AGENT_INTERNAL_KEY']}
    r=client.post('http://127.0.0.1:8001/internal/rag/questions/index',headers=headers,json={'questions':public});r.raise_for_status();release=r.json()['releaseId']
    deadline=time.monotonic()+120
    while True:
        state=client.get('http://127.0.0.1:8001/internal/rag/questions/index/'+release,headers=headers).json()['status']
        if state!='BUILDING':break
        imp.require(time.monotonic()<deadline,'日常题目索引准备超时');time.sleep(.25)
    imp.require(state=='READY','日常题目索引未就绪')
    # Health + local vector endpoints do not call the configured paid LLM.
    expected='rag-v1-'+__import__('hashlib').sha256(json.dumps(imp.corpus(),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
    imp.require(health['releaseId']==expected,'日常Agent仍使用旧语料')
    report=dict(redis_pid=redis_pid,java_pid=java.pid,agent_pid=agent.pid,frontend_pid=listener(5173),
        corpus_release=health['releaseId'],question_index_release=release,question_index_status=state,
        model_enabled=health['modelEnabled'],paid_model_calls=0,redis_existing_data_preserved=True)
    imp.dump(runtime/'processes.json',report)
    print(json.dumps(dict(report=str(runtime/'processes.json'),**report),ensure_ascii=False),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as e:
        print('启用失败：'+(str(e) if isinstance(e,RuntimeError) else type(e).__name__),file=sys.stderr);sys.exit(1)
