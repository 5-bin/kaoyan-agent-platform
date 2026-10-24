"""Real chat browser + process restart on isolated H2 and controlled SDK provider."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("smoke_helpers", ROOT / "scripts/smoke-current.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--node",default="node")
    parser.add_argument("--skip-browser",action="store_true")
    parser.add_argument("--timeout-check",action="store_true")
    parser.add_argument("--learning",action="store_true",help="Run actual learning assistant UI with disposable synthetic fixtures")
    parser.add_argument("--questions",action="store_true",help="Run question semantic-search UI with a real embedded Qdrant and explicit test vectors")
    args=parser.parse_args()
    if args.output.exists(): parser.error("报告已存在，请使用新路径")
    checks=[]
    with tempfile.TemporaryDirectory(prefix="kaoyan-chat-chain-") as folder:
        temp=Path(folder)
        python=java=frontend=None
        ports=set()
        while len(ports)<3: ports.add(helpers.free_port())
        py_port,java_port,front_port=ports
        py_base,java_base,front_base=[f"http://127.0.0.1:{port}" for port in (py_port,java_port,front_port)]
        env={**os.environ,"AGENT_INTERNAL_KEY":secrets.token_hex(32),"JWT_SECRET":secrets.token_hex(32),
            "AGENT_BASE_URL":py_base,"LLM_API_KEY":"","DB_PASSWORD":"","LLM_ENABLED":"false","RAG_BACKEND":"lexical",
            "LANGCHAIN_TRACING_V2":"false","LANGSMITH_TRACING":"false","MAX_MODEL_CALLS_PER_DAY":"200",
            "MINUTE_TASK_LIMIT":"30","NODE_PATH":str(ROOT/"kaoyan-frontend/node_modules")}
        cp=(ROOT/"kaoyan-B/target/test-classpath.txt").read_text().strip()
        classpath=os.pathsep.join([str(ROOT/"kaoyan-B/target/test-classes"),str(ROOT/"kaoyan-B/target/classes"),cp])
        handles=[(temp/name).open("w") for name in ("python.log","java.log","frontend.log")]
        try:
            python=subprocess.Popen([sys.executable,"-m","uvicorn","tests.chat_wire_app:app","--host","127.0.0.1","--port",str(py_port)],cwd=ROOT/"kaoyan-agent",env=env,stdout=handles[0],stderr=subprocess.STDOUT)
            helpers.wait_ready(python,py_base,"/health")
            command=["java","-cp",classpath,"com.kaoyan.AssistantSmokeServer" if args.learning or args.questions else "com.kaoyan.FrameworkSmokeServer","--server.address=127.0.0.1",f"--server.port={java_port}",
                "--spring.datasource.driver-class-name=org.h2.Driver",f"--spring.datasource.url=jdbc:h2:file:{temp}/chat;MODE=MySQL;NON_KEYWORDS=USER;WRITE_DELAY=0",
                "--spring.datasource.username=sa","--spring.datasource.password=","--spring.sql.init.mode=always","--spring.sql.init.schema-locations=classpath:schema-chain.sql,classpath:schema-practice.sql"]
            if args.questions: command.append("--kaoyan.smoke.questions=true")
            java=subprocess.Popen(command,cwd=temp,env=env,stdout=handles[1],stderr=subprocess.STDOUT)
            helpers.wait_ready(java,java_base,"/api/conversations",401)
            if not args.skip_browser:
                # Other workspace builds may replace dist while this check is running.
                shutil.copytree(ROOT/"kaoyan-frontend/dist",temp/"frontend-dist")
                frontend=subprocess.Popen([args.node,"node_modules/vite/bin/vite.js","preview","--outDir",str(temp/"frontend-dist"),"--host","127.0.0.1","--port",str(front_port),"--strictPort"],
                    cwd=ROOT/"kaoyan-frontend",env={**env,"API_PROXY_TARGET":java_base},stdout=handles[2],stderr=subprocess.STDOUT)
                helpers.wait_ready(frontend,front_base,"/")
                browser_args=[args.node,str(ROOT/("scripts/browser-question-search.cjs" if args.questions else "scripts/browser-learning.cjs" if args.learning else "scripts/browser-chat.cjs")),front_base]
                diagnostics=ROOT/".cache"/(("learning-browser-" if args.learning else "chat-browser-")+str(time.time_ns()))
                browser_args.append(str(diagnostics))
                browser=subprocess.run(browser_args,cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
                if browser.returncode: raise RuntimeError("隔离浏览器失败："+browser.stderr[-1200:])
                checks.extend(json.loads(browser.stdout.strip())["checks"])
            def call(path,method="GET",body=None,token=""):
                status,value=helpers.call(java_base,"/api"+path,method,body,token)
                if status!=200: raise AssertionError("chat smoke HTTP "+str(status))
                return value["data"]
            account={"username":"restart_chat","password":"test-only-chat-password"}
            call("/auth/register","POST",account)
            token=call("/auth/login","POST",account)["accessToken"]
            settings=call("/privacy/settings",token=token)
            call("/privacy/settings","PUT",{"modelAllowed":True,"scopes":["profile","document"],"provider":settings["provider"]},token)
            if args.timeout_check:
                timeout_id=call("/conversations","POST",token=token)["id"]
                call(f"/conversations/{timeout_id}/messages","POST",{"query":"进程与线程，等待停止","clientRequestId":"timeout-check"},token)
                deadline=time.monotonic()+51
                while True:
                    timed=call(f"/conversations/{timeout_id}/messages",token=token)["list"][0]["attempts"][0]
                    if timed["status"]!="RUNNING": break
                    if time.monotonic()>deadline: raise AssertionError("流程期限未生效")
                    time.sleep(.5)
                assert timed["status"]=="FAILED" and timed["draft"]=={}
                checks.append("actual_flow_timeout_persists_failure_and_clears_draft")
            conversation=call("/conversations","POST",token=token)["id"]
            attempt=call(f"/conversations/{conversation}/messages","POST",{"query":"进程与线程，等待停止","clientRequestId":"restart-check"},token)
            helpers.stop(java)
            java=subprocess.Popen(command,cwd=temp,env=env,stdout=handles[1],stderr=subprocess.STDOUT)
            helpers.wait_ready(java,java_base,"/api/conversations",401)
            deadline=time.monotonic()+10
            while True:
                data=call(f"/conversations/{conversation}/messages",token=token)
                saved=data["list"][0]["attempts"][0]
                if saved["status"]=="FAILED": break
                if time.monotonic()>deadline: raise AssertionError("chat restart recovery timeout")
                time.sleep(.1)
            assert saved["taskId"]==attempt["taskId"] and saved["draft"]=={}
            checks.append("actual_java_restart_preserves_conversation_and_interrupts_generation")
        except Exception:
            debug=ROOT/".cache"/("chat-debug-"+str(time.time_ns())); debug.mkdir(parents=True)
            for handle in handles: handle.flush()
            for name in ("python.log","java.log","frontend.log"): shutil.copyfile(temp/name,debug/name)
            print("隔离日志：",debug,file=sys.stderr)
            raise
        finally:
            for process in (frontend,java,python): helpers.stop(process)
            for handle in handles: handle.close()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({"scope":"actual Java/Python/LangChain; provider and Redis doubles; isolated H2", "checks":checks},ensure_ascii=False,indent=2))
    print(f"通过{len(checks)}项真实聊天链路检查：{args.output}")


if __name__=="__main__": main()
