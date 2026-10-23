"""Infrastructure scoped exclusively to kaoyan_feature_test_2027."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime

import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=ROOT/'.cache/feature-env-2027'
DATABASE='kaoyan_feature_test_2027'
DB_ACCOUNT='kaoyan_fixture_2027'
BASE='http://127.0.0.1:18080'
FRONT='http://127.0.0.1:15173'
MIGRATIONS=['V1__init.sql','V7__practice_snapshot.sql','V8__task_soft_delete.sql',
            'V9__question_source.sql','V10__chat_conversation.sql','V11__personal_document.sql',
            'V12__assistant_privacy.sql']


def require(ok,message):
    if not ok: raise RuntimeError(message)


def sql(value):
    if value is None: return 'NULL'
    if isinstance(value,(int,float)): return str(value)
    return "_utf8mb4 X'"+str(value).encode().hex()+"'"


def save(path,data):
    """Atomic private metadata; never prints secret values."""
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(path.parent,0o700)
    temporary=path.with_name(path.name+'.tmp')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as out: json.dump(data,out,ensure_ascii=False,indent=2)
    os.replace(temporary,path)


def load_config():
    path=PRIVATE/'config.json'
    require(path.exists(),'先运行 prepare --apply 创建独立环境配置')
    data=json.loads(path.read_text())
    require(data['DB_NAME']==DATABASE and data['DB_USER']==DB_ACCOUNT,'测试配置边界不符')
    require(data['DB_HOST'] in ('127.0.0.1','localhost','::1'),'只允许本机数据库')
    return data


class Database:
    def __init__(self,values):
        require(values.get('DB_HOST','127.0.0.1') in ('127.0.0.1','localhost','::1'),'只允许本机数据库')
        self.values=values
        self.env=os.environ.copy();self.env['MYSQL_PWD']=values.get('DB_PASSWORD') or ''
        self.options=['--protocol=TCP','--default-character-set=utf8mb4','-h',values.get('DB_HOST') or '127.0.0.1',
                      '-P',str(values.get('DB_PORT') or '3306'),'-u',values.get('DB_USER') or '']
        require(shutil.which('mysql') and shutil.which('mysqldump'),'缺少mysql或mysqldump')

    def query(self,statement,server=False):
        args=['mysql',*self.options,'--connect-timeout=5','-N','-B','--raw']
        if not server: args.append(DATABASE)
        result=subprocess.run(args,input=statement,env=self.env,text=True,capture_output=True,timeout=90)
        require(result.returncode==0,'MySQL操作失败（连接信息和SQL原始错误已隐藏）；未提交事务随连接关闭回滚')
        return result.stdout.strip()

    def rows(self,statement):
        return [json.loads(line) for line in self.query(statement).splitlines() if line]

    def backup(self):
        path=PRIVATE/('before-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.sql')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as out:
            result=subprocess.run(['mysqldump',*self.options,'--single-transaction','--no-tablespaces',
                '--set-gtid-purged=OFF','--column-statistics=0',DATABASE],env=self.env,stdout=out,stderr=subprocess.PIPE,timeout=90)
        require(result.returncode==0 and path.stat().st_size>0,'独立测试库备份失败，停止后续写入')
        return path


def prepare():
    PRIVATE.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(PRIVATE,0o700)
    configured=(PRIVATE/'config.json').exists()
    root=dotenv_values(ROOT/'.env')
    admin=Database(root)
    exists=admin.query(f'SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME={sql(DATABASE)};',server=True)=='1'
    if not configured:
        require(not exists,'同名数据库已存在但没有本机归属配置；拒绝接管')
        config=dict(DB_HOST=root.get('DB_HOST') or '127.0.0.1',DB_PORT=root.get('DB_PORT') or '3306',
            DB_NAME=DATABASE,DB_USER=DB_ACCOUNT,DB_PASSWORD=secrets.token_urlsafe(30),
            JWT_SECRET=secrets.token_urlsafe(48),AGENT_INTERNAL_KEY=secrets.token_urlsafe(32),
            REDIS_PASSWORD=secrets.token_urlsafe(30),environmentId=secrets.token_hex(16),databaseReady=False)
        # Refuse an unrelated preexisting MySQL account; never reset its password.
        require(admin.query(f'SELECT COUNT(*) FROM mysql.user WHERE user={sql(DB_ACCOUNT)};',server=True)=='0',
                '测试数据库账号名称已被占用；拒绝改密或接管')
        save(PRIVATE/'config.json',config)
    else: config=load_config()
    if not exists:
        admin.query(f'CREATE DATABASE `{DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;',server=True)
    # Provision only our generated account, granting permissions on the fixed test database.
    if not config.get('databaseReady'):
        account_exists=admin.query(f'SELECT COUNT(*) FROM mysql.user WHERE user={sql(DB_ACCOUNT)} AND host=\'127.0.0.1\';',server=True)=='1'
        if not account_exists:
            password=config['DB_PASSWORD'] # token_urlsafe: no quoting/control characters
            admin.query(f"CREATE USER '{DB_ACCOUNT}'@'127.0.0.1' IDENTIFIED BY '{password}';",server=True)
        admin.query(f"GRANT ALL PRIVILEGES ON `{DATABASE}`.* TO '{DB_ACCOUNT}'@'127.0.0.1';",server=True)
        config['databaseReady']=True;save(PRIVATE/'config.json',config)
    db=Database(config)
    tables=db.query('SHOW TABLES;').splitlines()
    if 'fixture_environment' not in tables:
        require(not tables,'非空库缺少独立测试归属标记；禁止运行V1')
        db.query('CREATE TABLE fixture_environment (id INT PRIMARY KEY, identity_value VARCHAR(64) NOT NULL);'
            f'INSERT INTO fixture_environment VALUES (1,{sql(config["environmentId"])});'
            'CREATE TABLE fixture_migration (name VARCHAR(100) PRIMARY KEY,checksum CHAR(64),state VARCHAR(20));'
            'CREATE TABLE fixture_item (kind VARCHAR(32),code VARCHAR(100),entity_id VARCHAR(64),'
            'state VARCHAR(32),checksum CHAR(64),PRIMARY KEY(kind,code));')
    require(db.query('SELECT identity_value FROM fixture_environment WHERE id=1;')==config['environmentId'],
            '测试库归属标记不匹配')
    if tables: db.backup()
    for name in MIGRATIONS:
        content=(ROOT/'kaoyan-B/src/main/resources/db'/name).read_text()
        checksum=hashlib.sha256(content.encode()).hexdigest()
        existing=db.query(f'SELECT CONCAT(state,CHAR(9),checksum) FROM fixture_migration WHERE name={sql(name)};')
        if existing:
            require(existing=='done\t'+checksum,'迁移内容改变或曾部分失败，停止；不会重跑V1或自动清库')
            continue
        if name.startswith('V1__'):
            allowed={'fixture_environment','fixture_migration','fixture_item'}
            require(set(db.query('SHOW TABLES;').splitlines())==allowed,'V1仅允许在只有测试元数据的空业务库执行')
        db.query(f'INSERT INTO fixture_migration VALUES ({sql(name)},{sql(checksum)},\'started\');')
        db.query(content+f'\nUPDATE fixture_migration SET state=\'done\' WHERE name={sql(name)};')
    # V1 specifies utf8mb4 explicitly while V10+ inherit the database default.
    # Align a newly initialized, still-empty test database; never rewrite a used database.
    collations=db.query('SELECT TABLE_NAME,TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE();')
    mismatched=[row.split('\t')[0] for row in collations.splitlines() if not row.endswith('\tutf8mb4_0900_ai_ci')]
    if mismatched:
        business=[t for t in db.query('SHOW TABLES;').splitlines() if not t.startswith('fixture_')]
        require(all(db.query(f'SELECT COUNT(*) FROM `{t}`;')=='0' for t in business),
                '已使用的测试库存在混合排序规则，停止；不会转换已有业务数据')
        db.backup()
        db.query(f'ALTER DATABASE `{DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;')
        for table in mismatched:
            require(table.replace('_','').isalnum(),'非法表名')
            db.query(f'ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;')
    # Credentials are generated before registration so interrupted runs can resume safely.
    if not (PRIVATE/'credentials.json').exists():
        names={'admin':'fixture_admin_2027','demo':'fixture_student_2027','empty':'fixture_empty_2027'}
        require(db.query('SELECT COUNT(*) FROM user;')=='0','已有账号但缺少私密凭据，拒绝接管')
        save(PRIVATE/'credentials.json',{k:dict(username=v,password=secrets.token_urlsafe(18)) for k,v in names.items()})
    print('独立测试库结构就绪；当前业务库未写入。',flush=True)


def runtime_env():
    c=load_config()
    env=os.environ.copy()
    # Override inherited/root dotenv settings; do not copy normal provider credentials.
    env.update({k:str(v) for k,v in c.items() if k.isupper()})
    env.update(SPRING_PROFILES_ACTIVE='feature-test',PORT='18080',
        SPRING_DATASOURCE_URL=f'jdbc:mysql://{c["DB_HOST"]}:{c["DB_PORT"]}/{DATABASE}?serverTimezone=Asia/Shanghai&useUnicode=true&characterEncoding=utf-8&useSSL=false&allowPublicKeyRetrieval=true',
        SPRING_DATASOURCE_USERNAME=DB_ACCOUNT,SPRING_DATASOURCE_PASSWORD=c['DB_PASSWORD'],
        SPRING_DATA_REDIS_HOST='127.0.0.1',SPRING_DATA_REDIS_PORT='16379',SPRING_DATA_REDIS_PASSWORD=c['REDIS_PASSWORD'],
        AGENT_BASE_URL='http://127.0.0.1:18001',LLM_ENABLED='false',LLM_API_KEY='',LLM_BASE_URL='https://example.invalid',
        RAG_BACKEND='lexical',RAG_DATA=str(PRIVATE/'corpus.json'),RAG_INDEX=str(PRIVATE/'rag'),
        QDRANT_URL='',QDRANT_API_KEY='',API_PROXY_TARGET=BASE,
        PYTHON_EXECUTABLE=sys.executable)
    return env


def occupied(port):
    with socket.socket() as s:
        s.settimeout(.2);return s.connect_ex(('127.0.0.1',port))==0


def identity(pid):
    result=subprocess.run(['ps','-p',str(pid),'-o','lstart=','-o','command='],text=True,capture_output=True)
    return result.stdout.strip() if result.returncode==0 else ''


def process_state():
    path=PRIVATE/'processes.json'
    return json.loads(path.read_text()) if path.exists() else {}


def owned(item):
    return bool(item and identity(item['pid'])==item['identity'])


def stop_one(name):
    states=process_state();item=states.get(name)
    require(owned(item),'拒绝停止不属于本次独立环境的进程')
    os.kill(item['pid'],signal.SIGTERM)
    for _ in range(100):
        if not owned(item): break
        time.sleep(.1)
    require(not owned(item),'本次服务未及时停止；未发送强制终止信号')
    states.pop(name,None);save(PRIVATE/'processes.json',states)


def start():
    c=load_config();env=runtime_env()
    require(identity(os.getpid()),'需要读取本次进程身份，未启动任何新服务')
    require((PRIVATE/'corpus.json').exists(),'先生成并校验专用语料')
    require(shutil.which('redis-server'),'缺少redis-server')
    ports={'redis':16379,'agent':18001,'backend':18080,'frontend':15173}
    states=process_state()
    for name,port in ports.items():
        if owned(states.get(name)): continue
        require(not occupied(port),f'专用端口{port}被其他服务占用；没有停止已有服务')
    redis_dir=PRIVATE/'redis';redis_dir.mkdir(mode=0o700,exist_ok=True)
    conf=PRIVATE/'redis.conf'
    if not conf.exists():
        fd=os.open(conf,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as out:
            out.write(f'bind 127.0.0.1\nport 16379\nprotected-mode yes\nrequirepass {c["REDIS_PASSWORD"]}\ndir "{redis_dir}"\nappendonly yes\n')
    jar=ROOT/'kaoyan-B/target/kaoyan-backend-1.0.0.jar'
    require(jar.exists(),'先构建当前后端JAR')
    commands={
        'redis':(['redis-server',str(conf)],ROOT),
        'agent':([sys.executable,'-m','uvicorn','main:create_app','--factory','--host','127.0.0.1','--port','18001'],ROOT/'kaoyan-agent'),
        'backend':(['java','-jar',str(jar),'--server.port=18080','--server.address=127.0.0.1','--spring.application.name=feature-test-2027'],ROOT/'kaoyan-B'),
        'frontend':(['node','node_modules/vite/bin/vite.js','preview','--host','127.0.0.1','--port','15173','--strictPort'],ROOT/'kaoyan-frontend')}
    started=[]
    try:
        for name,port in ports.items():
            if owned(states.get(name)): continue
            fd=os.open(PRIVATE/(name+'.log'),os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
            with os.fdopen(fd,'ab') as out:
                args,cwd=commands[name]
                proc=subprocess.Popen(args,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
            time.sleep(.1)
            sig=identity(proc.pid);require(sig,f'{name}启动立即失败；见私密日志')
            states[name]=dict(pid=proc.pid,identity=sig,port=port);save(PRIVATE/'processes.json',states);started.append(name)
            with httpx.Client(trust_env=False,timeout=2) as client:
                for _ in range(240):
                    require(proc.poll() is None,f'{name}进程退出，见私密日志')
                    ready=occupied(port)
                    if name=='agent' and ready:
                        try: ready=client.get('http://127.0.0.1:18001/health').status_code==200
                        except httpx.HTTPError: ready=False
                    if name=='backend' and ready:
                        try: ready=client.post(BASE+'/api/auth/login',json={'username':'readiness_only','password':'not-a-real-password'}).status_code in (400,401)
                        except httpx.HTTPError: ready=False
                    if ready: break
                    time.sleep(.25)
                else: raise RuntimeError(f'{name}启动超时，见私密日志')
            print(name+'专用服务就绪',flush=True)
    except BaseException:
        for name in reversed(started):
            if owned(process_state().get(name)): stop_one(name)
        raise
    print('独立测试页面：'+FRONT,flush=True)


class Api:
    def __init__(self): self.client=httpx.Client(base_url=BASE,trust_env=False,timeout=55)
    def call(self,method,path,token=None,body=None,status=200):
        response=self.client.request(method,path,json=body,headers={'Authorization':'Bearer '+token} if token else {})
        require(response.status_code==status,f'接口{method} {path.split("?")[0]}：HTTP {response.status_code}，预期{status}')
        data=response.json()
        if status==200: require(data.get('code') in (0,200),'接口业务失败：'+path.split('?')[0])
        return data.get('data')
    def login(self,credential): return self.call('POST','/api/auth/login',body=credential)['accessToken']
