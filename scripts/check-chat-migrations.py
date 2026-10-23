"""Validate V10/V11/V12 on a disposable MySQL server; never connect to daily MySQL."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("报告已存在，请使用新路径")
    server_bin, client_bin = shutil.which("mysqld"), shutil.which("mysql")
    if not server_bin or not client_bin:
        parser.error("需要已安装的mysqld及mysql；此脚本不会安装软件或访问已有服务")
    checks = []
    with tempfile.TemporaryDirectory(prefix="kaoyan-chat-mysql-") as folder:
        temporary = Path(folder)
        data, socket = temporary / "data", temporary / "mysql.sock"
        log = temporary / "server.log"
        with log.open("w") as out:
            initialized = subprocess.run([server_bin,"--no-defaults","--initialize-insecure",f"--datadir={data}"],stdout=out,stderr=subprocess.STDOUT)
            if initialized.returncode:
                out.flush()
                raise RuntimeError("隔离MySQL初始化失败：" + log.read_text()[-1800:])
            process = subprocess.Popen([server_bin,"--no-defaults",f"--datadir={data}",f"--socket={socket}",
                "--skip-networking","--skip-log-bin",f"--pid-file={temporary / 'mysql.pid'}"],stdout=out,stderr=subprocess.STDOUT)
            command = [client_bin,"--no-defaults","--protocol=SOCKET",f"--socket={socket}","--user=root","--batch","--skip-column-names"]
            def sql(text, expected=True):
                result = subprocess.run(command,input=text,text=True,capture_output=True,timeout=15)
                if (result.returncode == 0) != expected:
                    raise AssertionError("隔离MySQL语句结果不符合预期：" + result.stderr[:300])
                return result.stdout.strip()
            try:
                for _ in range(100):
                    ready = subprocess.run(command,input="SELECT 1",text=True,capture_output=True)
                    if ready.returncode == 0:
                        break
                    if process.poll() is not None:
                        raise RuntimeError("隔离MySQL启动失败")
                    time.sleep(0.1)
                else:
                    raise RuntimeError("隔离MySQL启动超时")
                sql("CREATE DATABASE chat_test CHARACTER SET utf8mb4; USE chat_test; CREATE TABLE task(id VARCHAR(36) PRIMARY KEY,marker VARCHAR(50)); INSERT INTO task VALUES('old-task','preserve-existing');")
                for name in ("V10__chat_conversation.sql","V11__personal_document.sql","V12__assistant_privacy.sql"):
                    sql("USE chat_test;\n" + (ROOT/"kaoyan-B/src/main/resources/db"/name).read_text())
                    checks.append(name)
                assert sql("USE chat_test; SELECT marker FROM task WHERE id='old-task';") == "preserve-existing"
                checks.append("existing_record_preserved")
                sql("USE chat_test; INSERT INTO chat_conversation(id,user_id,title,conditions_json,profile_json) VALUES('c',1,'线程','{}','{}'); INSERT INTO chat_message(id,conversation_id,user_id,sequence_no,content) VALUES('m','c',1,1,'问题');")
                sql("USE chat_test; INSERT INTO chat_message(id,conversation_id,user_id,sequence_no,content) VALUES('m2','c',1,1,'冲突');",False)
                checks.append("unique_message_sequence")
                def generation(task, request, attempt, active):
                    active = "NULL" if active is None else "'c'"
                    return f"USE chat_test; INSERT INTO chat_generation(task_id,conversation_id,message_id,user_id,attempt_no,client_request_id,request_hash,status,active_conversation_id,context_json,draft_json) VALUES('{task}','c','m',1,{attempt},'{request}','hash','RUNNING',{active},'{{}}','{{}}');"
                sql(generation("t1","request1",1,"c"))
                sql(generation("t2","request2",2,"c"),False)
                checks.append("unique_active_generation")
                sql("USE chat_test; UPDATE chat_generation SET status='CANCELLED',active_conversation_id=NULL WHERE task_id='t1' AND status='RUNNING';")
                sql(generation("t2","request2",2,"c"))
                sql(generation("t3","request2",3,None),False)
                checks.append("retry_and_request_id_uniqueness")
                assert sql("USE chat_test; UPDATE chat_generation SET status='SUCCESS',active_conversation_id=NULL WHERE task_id='t2' AND status='RUNNING'; SELECT ROW_COUNT();") == "1"
                assert sql("USE chat_test; UPDATE chat_generation SET status='CANCELLED' WHERE task_id='t2' AND status='RUNNING'; SELECT ROW_COUNT();") == "0"
                checks.append("single_terminal_state")
                sql("USE chat_test; INSERT INTO personal_document(id,user_id,title,content,version) VALUES('d',1,'笔记','原文',1); INSERT INTO personal_document_version(document_id,version,user_id,title,content,source_task_id) VALUES('d',1,1,'笔记','原文','t1');")
                sql("USE chat_test; INSERT INTO personal_document_version(document_id,version,user_id,title,content,source_task_id) VALUES('d',2,1,'重复','不应保存','t1');",False)
                checks.append("document_confirmation_uniqueness")
                sql("USE chat_test; INSERT INTO assistant_privacy(user_id,scopes_json,provider) VALUES(1,'{}','');")
                assert sql("USE chat_test; SELECT model_allowed FROM assistant_privacy WHERE user_id=1;")=="0"
                checks.append("privacy_defaults_off")
                sql("USE chat_test; INSERT INTO assistant_action(id,user_id,conversation_id,task_id,operation,status,payload_json,result_json) VALUES('a',1,'c','t1','FAVORITE_ADD','PENDING','{}','{}');")
                sql("USE chat_test; INSERT INTO assistant_action(id,user_id,conversation_id,task_id,operation,status,payload_json,result_json) VALUES('b',1,'c','t1','FAVORITE_ADD','PENDING','{}','{}');",False)
                checks.append("one_action_per_generation")
            finally:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({"scope":"disposable MySQL socket only; no daily database","checks":checks},ensure_ascii=False,indent=2))
    print(f"通过 {len(checks)} 项隔离MySQL检查：{args.output}")


if __name__ == "__main__":
    main()
