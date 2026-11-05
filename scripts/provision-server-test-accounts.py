"""Provision authorized synthetic test accounts, using Java for creation/grading.

Default preview is read-only. Passwords live only in an owner-only credentials
file. Resume follows a private journal and never resets or adopts existing users.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import time
from typing import Literal
import uuid
from zoneinfo import ZoneInfo

import httpx
from dotenv import dotenv_values

SUBJECTS = ("数据结构", "操作系统", "计算机组成原理", "计算机网络")
NAMES = tuple(f"test{i}" for i in range(1, 11))
FIXTURE = "server-study-fixture-v1-20261103"
HELPER_SHA = "bd0e9bd00ae786b1248c108b7105d65d7802f5e0e5657728eb43189b6a7d76cb"


def require(condition: object, message: str) -> None:
    """Stop with a credential-free operational error."""
    if not condition:
        raise RuntimeError(message)


def literal(value: object) -> str:
    """Quote controlled SQL values without command interpolation."""
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    return "CONVERT(0x" + str(value).encode().hex() + " USING utf8mb4)"


def save(path: Path, data: object) -> None:
    """Atomically persist private progress with fsync and owner-only permissions."""
    temporary = path.with_suffix(".new")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


@dataclass(frozen=True)
class Question:
    """Frozen reviewed question metadata, read only by the provisioning operator."""

    id: int
    subject: str
    point: str
    difficulty: str
    answer: str
    version: int


def select_questions(rows: list[dict]) -> list[Question]:
    """Select 20 per subject with difficulty coverage and topic round-robin."""
    result = []
    for subject in SUBJECTS:
        groups: dict[tuple[str, str], list[Question]] = defaultdict(list)
        for row in rows:
            question = Question(**row)
            if question.subject == subject:
                groups[(question.point, question.difficulty)].append(question)
        keys = sorted(groups)
        chosen = []
        for difficulty in ("EASY", "MEDIUM", "HARD"):
            candidates = [key for key in keys if key[1] == difficulty and groups[key]]
            require(candidates, "题库难度覆盖不足: " + subject)
            chosen.append(groups[candidates[0]].pop(0))
        while len(chosen) < 20:
            progressed = False
            for key in keys:
                if groups[key] and len(chosen) < 20:
                    chosen.append(groups[key].pop(0))
                    progressed = True
            require(progressed, "审核题目不足: " + subject)
        result.extend(chosen)
    require(len({q.id for q in result}) == 80, "题目集合重复")
    return result


def correct_per_round(account: int, subject: int, week: int) -> int:
    """Return the exact planned correct count for one 20-question batch."""
    weak = (account - 1) % 4
    offset = (subject - weak) % 4
    base = 6 + 2 * ((account - 1) // 4) if offset == 0 else (12, 14, 16)[offset - 1]
    return base + week - 2


def planned_answer(question: Question, account: int, subject: int, week: int, index: int) -> str:
    """Choose an answer; Java remains the authority for actual grading."""
    correct = (index + 3 * week + account) % 20 < correct_per_round(account, subject, week)
    return question.answer if correct else next(option for option in "ABCD" if option != question.answer)


class Provisioner:
    """Bound a single authorized run to a frozen roster, questions and journal."""

    def __init__(self, db: object, helper: object, release: Path, output: Path,
                 credentials: dict[str, str], base_url: str = "http://127.0.0.1:8080") -> None:
        """Inject DB and API dependencies; initialization performs no writes."""
        self.db = db
        self.helper = helper
        self.release = release
        self.output = output
        self.credentials = credentials
        self.client = httpx.Client(base_url=base_url, timeout=30, trust_env=False)
        self.state_path = output / "progress.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else None

    def close(self) -> None:
        """Release the local HTTP transport without retaining tokens."""
        self.client.close()

    def rows(self, sql: str) -> list[dict]:
        """Read selected metadata as JSON, without printing result contents."""
        return [json.loads(line) for line in self.db.query(sql).splitlines() if line]

    def api(self, method: str, path: str, token: str = "", body: object = None,
            status: int = 200) -> object:
        """Call the bound Java API, suppressing tokens, bodies and error details."""
        response = self.client.request(method, "/api" + path, json=body,
                                       headers={"Authorization": "Bearer " + token} if token else {})
        require(response.status_code == status, "API失败: " + path + " HTTP=" + str(response.status_code))
        envelope = response.json()
        if status == 200:
            require(envelope.get("code") == 0, "API业务失败: " + path)
        return envelope.get("data")

    def checkpoint(self) -> None:
        """Flush only noncredential run state after each irreversible business step."""
        save(self.state_path, self.state)

    def questions(self) -> list[Question]:
        """Read the currently reviewed and nonwithdrawn single-choice pool."""
        rows = self.rows("SELECT JSON_OBJECT('id',q.id,'subject',q.subject,'point',q.knowledge_point,'difficulty',q.difficulty,'answer',q.answer,'version',q.version) FROM question q WHERE q.review_status='APPROVED' AND q.active=1 AND q.question_type='SINGLE_CHOICE' AND q.answer IN ('A','B','C','D') AND NOT EXISTS (SELECT 1 FROM question_version v WHERE v.question_id=q.id AND v.version=q.version AND v.withdrawn=1) ORDER BY q.id;")
        return select_questions(rows)

    def preview(self) -> dict:
        """Return counts and occupied names; do not allocate files or business rows."""
        questions = self.questions()
        occupied = self.db.query("SELECT username FROM `user` WHERE username IN (" + ",".join(map(literal, NAMES)) + ") ORDER BY username;").splitlines()
        return {"names": list(NAMES), "occupiedNames": occupied, "questions": len(questions), "attemptsPerAccount": 400, "sessionsPerAccount": 20, "favoritesPerAccount": 16, "modelCalls": 0}

    def prepare(self) -> None:
        """Verify a full backup restore before starting any new-account writes."""
        require(set(self.credentials) == set(NAMES), "凭证必须恰为十个指定用户名")
        if self.state is not None:
            require(self.state["fixture"] == FIXTURE and set(self.state["accounts"]) == set(NAMES), "执行日志不匹配")
            require(self.state["backupVerified"] is True, "未验证备份")
            return
        preview = self.preview()
        require(not preview["occupiedNames"], "用户名已存在，禁止接管或重设密码")
        questions = self.questions()
        self.output.mkdir(mode=0o700, exist_ok=False)
        backup = self.output / "backup"
        backup.mkdir(mode=0o700)
        data = self.release / "public-data/public-content.json"
        source = json.loads(data.read_text())["tables"]
        plan, pending = self.helper.inspect(self.db, source, self.release)
        require(not pending and not any(plan.inserts.values()) and not plan.updates, "服务器资料或结构与当前版本不符")
        report = self.helper.summary(plan, pending, hashlib.sha256(data.read_bytes()).hexdigest())
        self.helper.rehearse(self.db, source, self.release, backup, report)
        save(backup / "report.json", report)
        self.state = {"fixture": FIXTURE, "runId": uuid.uuid4().hex, "backupVerified": True,
                      "anchor": (datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None) - timedelta(hours=4)).isoformat(),
                      "questions": [asdict(q) for q in questions], "accounts": {name: {"ownerId": None, "creationStarted": False, "sessions": {}} for name in NAMES}}
        self.checkpoint()

    def token(self, name: str) -> str:
        """Authenticate privately and enforce the journal's exact STUDENT identity."""
        token = self.api("POST", "/auth/login", body={"username": name, "password": self.credentials[name]})["accessToken"]
        me = self.api("GET", "/users/me", token)
        account = self.state["accounts"][name]
        require(me["username"] == name and me["role"] == "STUDENT" and me["status"] == 1, "账号身份不符")
        require(account["ownerId"] is None or int(me["id"]) == account["ownerId"], "账号ID与日志不符")
        if account["ownerId"] is None:
            require(account["creationStarted"], "没有创建意图，禁止接管账号")
            account["ownerId"] = int(me["id"])
            self.checkpoint()
        return token

    def create(self) -> None:
        """Create only fresh users, or resume a previously journaled create intent."""
        self.prepare()
        for index, name in enumerate(NAMES, 1):
            account = self.state["accounts"][name]
            exists = int(self.db.query("SELECT COUNT(*) FROM `user` WHERE username=" + literal(name) + ";"))
            if not account["creationStarted"]:
                require(exists == 0, "用户名在预检后被占用")
                account["creationStarted"] = True
                self.checkpoint()
            if not exists:
                self.api("POST", "/auth/register", body={"username": name, "password": self.credentials[name]})
            token = self.token(name)
            try:
                self.api("PUT", "/users/profile", token, {"examYear": 2027, "targetMajor": "081200", "degreeType": "academic", "background": "【模拟刷题测试账号】" + FIXTURE + "；近28天400次合成作答，用于功能测试，不代表真实学习；薄弱科目：" + SUBJECTS[(index - 1) % 4] + "。未授权模型外发。"})
                account["created"] = True
                self.checkpoint()
            finally:
                self.api("POST", "/auth/logout", token)
            print("账号创建核对: " + name, flush=True)

    def session(self, name: str, token: str, week: int, subject_index: int, group: list[Question]) -> str:
        """Recover an uncertain session creation using the journal's before-set."""
        account = self.state["accounts"][name]
        owner = account["ownerId"]
        key = f"{week}:{subject_index}"
        sessions = account["sessions"]
        if key not in sessions:
            before = self.db.query(f"SELECT id FROM practice_session WHERE user_id={owner} ORDER BY id;").splitlines()
            sessions[key] = {"id": None, "before": before}
            self.checkpoint()
        entry = sessions[key]
        if entry["id"] is None:
            current = self.db.query(f"SELECT id FROM practice_session WHERE user_id={owner} ORDER BY id;").splitlines()
            candidates = set(current) - set(entry["before"])
            require(len(candidates) <= 1, "待恢复批次不唯一，禁止重复创建")
            if candidates:
                entry["id"] = next(iter(candidates))
            else:
                entry["id"] = self.api("POST", "/practice/sessions", token, {"subject": SUBJECTS[subject_index], "count": 20, "source": "NORMAL", "questionIds": [q.id for q in group]})["sessionId"]
            self.checkpoint()
        state = self.api("GET", f'/practice/sessions/{entry["id"]}/state', token)
        require(set(int(item["questionId"]) for item in state["items"]) == {q.id for q in group}, "批次题目与日志不符")
        return entry["id"]

    def seed(self) -> None:
        """Submit planned answers exactly once and project only journaled histories."""
        require(self.state is not None and all(a.get("created") for a in self.state["accounts"].values()), "账号创建尚未完成")
        questions = [Question(**q) for q in self.state["questions"]]
        require([asdict(q) for q in self.questions()] == self.state["questions"], "审核题库已变化，需要人工核对")
        for account_index, name in enumerate(NAMES, 1):
            account = self.state["accounts"][name]
            token = self.token(name)
            try:
                if not account.get("seeded"):
                    for week in range(5):
                        for subject_index, subject in enumerate(SUBJECTS):
                            group = [q for q in questions if q.subject == subject]
                            session = self.session(name, token, week, subject_index, group)
                            state = self.api("GET", f"/practice/sessions/{session}/state", token)
                            items = {int(item["questionId"]): item for item in state["items"]}
                            answers = []
                            for index, question in enumerate(group):
                                item = items[question.id]
                                answer = planned_answer(question, account_index, subject_index, week, index)
                                request_id = uuid.uuid5(uuid.NAMESPACE_URL, f'{self.state["runId"]}/{name}/{week}/{subject_index}/{question.id}').hex
                                if item["submitted"]:
                                    require(item["userAnswer"] == answer and item["isCorrect"] == int(answer == question.answer), "已有作答与计划不符，禁止覆盖")
                                else:
                                    result = self.api("POST", f"/practice/sessions/{session}/answer", token, {"questionId": question.id, "itemId": item["itemId"], "answer": answer, "clientRequestId": request_id})
                                    require(int(result["isCorrect"]) == int(answer == question.answer), "服务器判分与冻结版本不符")
                                answers.append({"itemId": item["itemId"], "questionId": question.id, "requestId": request_id})
                            final = self.api("GET", f"/practice/sessions/{session}/state", token)
                            require(final["state"] == "FINISHED", "批次未结束")
                            account["sessions"][f"{week}:{subject_index}"]["answers"] = answers
                            self.checkpoint()
                        print(name + " 正式判分 " + str((week + 1) * 80) + "/400", flush=True)
                    for subject in SUBJECTS:
                        for question in [q for q in questions if q.subject == subject][:4]:
                            favorite = self.db.query(f"SELECT is_favorite FROM user_question_mark WHERE user_id={account['ownerId']} AND question_id={question.id};")
                            if favorite != "1":
                                self.api("POST", f"/marks/favorite/{question.id}", token)
                    self.project(name)
                    account["seeded"] = True
                    self.checkpoint()
                account["verified"] = self.verify_account(name, token)
                self.checkpoint()
            finally:
                self.api("POST", "/auth/logout", token)

    def project(self, name: str) -> None:
        """Apply one guarded short transaction to this run's new-account records."""
        account = self.state["accounts"][name]
        owner = account["ownerId"]
        sessions = account["sessions"]
        expected_ids = {entry["id"] for entry in sessions.values()}
        actual_ids = set(self.db.query(f"SELECT id FROM practice_session WHERE user_id={owner};").splitlines())
        require(len(expected_ids) == 20 and actual_ids == expected_ids, "存在日志以外的批次，禁止历史投影")
        require(self.db.query(f"SELECT COUNT(*) FROM practice_record WHERE user_id={owner};") == "400", "作答数量不符")
        require(self.db.query(f"SELECT username FROM `user` WHERE id={owner};") == name, "账号ID已改变")
        statements = ["START TRANSACTION;", f"SELECT id FROM `user` WHERE id={owner} AND username={literal(name)} FOR UPDATE;"]
        anchor = datetime.fromisoformat(self.state["anchor"])
        for key, entry in sessions.items():
            week, subject = map(int, key.split(":"))
            start = anchor - timedelta(days=7 * (4 - week)) + timedelta(minutes=45 * subject)
            finish = start + timedelta(minutes=39)
            sid = literal(entry["id"])
            statements.append(f"UPDATE practice_session SET created_at={literal(start)},finished_at={literal(finish)} WHERE user_id={owner} AND id={sid} AND state='FINISHED';")
            for index, answer in enumerate(entry["answers"]):
                at = literal(start + timedelta(minutes=2 * index + 1))
                record = int(answer["itemId"])
                statements.append(f"UPDATE practice_record SET created_at={literal(start)},answered_at={at},question_snapshot=JSON_SET(question_snapshot,'$.fixture',{literal(FIXTURE)},'$.syntheticHistory',CAST('true' AS JSON)) WHERE user_id={owner} AND session_id={sid} AND id={record} AND is_correct IS NOT NULL AND grading_status='valid';")
                statements.append(f"UPDATE practice_session_item i JOIN practice_record r ON r.id=i.record_id SET i.submitted_at={at} WHERE r.user_id={owner} AND r.session_id={sid} AND r.id={record};")
                statements.append(f"UPDATE practice_request SET created_at={at} WHERE user_id={owner} AND request_id={literal(answer['requestId'])};")
        statements.append(f"UPDATE user_question_mark m SET last_wrong_at=(SELECT MAX(r.answered_at) FROM practice_record r WHERE r.user_id={owner} AND r.question_id=m.question_id AND r.is_correct=0 AND r.grading_status='valid') WHERE m.user_id={owner} AND m.is_wrong=1;")
        event_key = literal(str(owner) + ":" + self.state["runId"] + ":history")
        now = literal(datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None))
        statements.append(f"INSERT INTO learning_event(id,user_id,event_key,state,next_at,created_at) VALUES({literal(str(uuid.uuid4()))},{owner},{event_key},'PENDING',{now},{now}) ON DUPLICATE KEY UPDATE state='PENDING',attempts=0,next_at={now};")
        statements.append("COMMIT;")
        self.db.query("\n".join(statements))

    def verify_account(self, name: str, token: str) -> dict:
        """Check counts, identity, privacy, statistics and real worker recomputation."""
        account = self.state["accounts"][name]
        owner = account["ownerId"]
        index = NAMES.index(name) + 1
        correct = sum(correct_per_round(index, subject, week) for week in range(5) for subject in range(4))
        require(self.db.query(f"SELECT COUNT(*) FROM practice_record WHERE user_id={owner} AND grading_status='valid' AND is_correct IS NOT NULL AND JSON_UNQUOTE(JSON_EXTRACT(question_snapshot,'$.fixture'))={literal(FIXTURE)};") == "400", "快照或有效作答不符")
        require(self.db.query(f"SELECT COUNT(*) FROM practice_session WHERE user_id={owner} AND state='FINISHED';") == "20", "结束批次不符")
        require(self.db.query(f"SELECT COUNT(*) FROM practice_record r JOIN practice_session_item i ON r.id=i.record_id WHERE r.user_id={owner} AND (r.answered_at<>i.submitted_at OR r.answered_at>{literal(datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None))});") == "0", "日期不一致或存在未来作答")
        overview = self.api("GET", "/stats/overview", token)
        require(overview["totalQuestions"] == 400 and overview["totalCorrect"] == correct, "总统计不符")
        profile = None
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            profile = self.api("GET", "/learning/profile", token)
            if profile["independentSamples"] == 400 and self.db.query(f"SELECT COUNT(*) FROM learning_event WHERE user_id={owner} AND event_key={literal(str(owner)+':'+self.state['runId']+':history')} AND state='DONE';") == "1":
                break
            time.sleep(1)
        require(profile["independentSamples"] == 400 and profile["unknownSamples"] == 0 and profile["assistedSamples"] == 0, "画像未完成重算")
        require(all(group["samples"] >= 5 for group in profile["groups"] if group["samples"] > 0), "画像独立样本不足")
        favorites = self.api("GET", "/marks/favorite?pageNum=1&pageSize=10", token)
        wrong = self.api("GET", "/marks/wrong?pageNum=1&pageSize=10", token)
        require(favorites["total"] == 16, "收藏数量不符")
        expected_wrong = int(self.db.query(f"SELECT COUNT(DISTINCT question_id) FROM practice_record WHERE user_id={owner} AND is_correct=0 AND grading_status='valid';"))
        require(wrong["total"] == expected_wrong, "错题统计不符")
        privacy = self.api("GET", "/privacy/settings", token)
        require(privacy["modelAllowed"] is False, "模型授权不能被启用")
        require(self.db.query(f"SELECT COUNT(*) FROM learning_recommendation_settings WHERE user_id={owner} AND enabled=1;") == "0", "自动推荐不得启用")
        self.api("GET", "/admin/questions?pageNum=1&pageSize=1", token, status=403)
        return {"attempts": 400, "correct": correct, "accuracy": correct / 400, "sessions": 20, "favorites": 16, "wrong": wrong["total"], "independentSamples": profile["independentSamples"], "groups": len(profile["groups"]), "weakSubject": SUBJECTS[(index - 1) % 4], "synthetic": True, "modelAllowed": False}

    def verify(self) -> dict:
        """Verify every account plus ownership boundaries and log out all tokens."""
        require(self.state is not None, "缺少执行日志")
        tokens = {}
        try:
            result = {}
            for name in NAMES:
                tokens[name] = self.token(name)
                result[name] = self.verify_account(name, tokens[name])
            for index, name in enumerate(NAMES):
                other = NAMES[(index + 1) % len(NAMES)]
                sid = self.state["accounts"][other]["sessions"]["0:0"]["id"]
                self.api("GET", f"/practice/sessions/{sid}/state", tokens[name], status=404)
            report = {"accounts": result, "crossAccount404": True, "studentAdmin403": True, "modelsCalled": 0}
            save(self.output / "verification.json", report)
            return report
        finally:
            for token in tokens.values():
                self.api("POST", "/auth/logout", token)


def main() -> None:
    """Bind production execution to this server and a private, explicit run directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--data-helper", type=Path, required=True)
    parser.add_argument("--expected-db", required=True)
    parser.add_argument("--stage", choices=("preview", "create", "seed", "verify"), default="preview")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    require(socket.gethostname() == "iZj6cb4euf28b560hanyr7Z" and os.geteuid() == 0, "仅支持已授权服务器root")
    require(args.output.parent == Path("/root") and not args.output.is_symlink(), "执行目录边界不符")
    require(args.release_root.resolve().parent == Path("/opt/kaoyan-releases"), "发布目录边界不符")
    require(args.credentials.is_file() and not args.credentials.is_symlink() and args.credentials.stat().st_mode & 0o077 == 0, "凭证文件必须私密且不可为符号链接")
    require(hashlib.sha256(args.data_helper.read_bytes()).hexdigest() == HELPER_SHA, "数据工具版本不符")
    spec = importlib.util.spec_from_file_location("provision_data_helper", args.data_helper)
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    spec.loader.exec_module(helper)
    values = dotenv_values("/opt/kaoyan/.env")
    require(values["DB_NAME"] == args.expected_db and values.get("LLM_ENABLED", "false").lower() == "false", "数据库或模型配置不符")
    environment = os.environ.copy()
    environment.pop("MYSQL_PWD", None)
    db = helper.Database(args.expected_db, ["--protocol=SOCKET", "--user=root", "--default-character-set=utf8mb4"], environment)
    credentials = json.loads(args.credentials.read_text())
    require(set(credentials) == set(NAMES), "凭证用户名集合不符")
    if args.output.exists():
        require(args.output.stat().st_mode & 0o077 == 0, "执行目录必须私密")
    obj = Provisioner(db, helper, args.release_root, args.output, credentials)
    try:
        if not args.apply or args.stage == "preview":
            print(json.dumps(obj.preview(), ensure_ascii=False), flush=True)
        elif args.stage == "create":
            obj.create()
        elif args.stage == "seed":
            obj.seed()
        else:
            print(json.dumps(obj.verify(), ensure_ascii=False), flush=True)
    finally:
        obj.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(str(error) if isinstance(error, RuntimeError) else "执行失败，异常类别=" + type(error).__name__) from None
