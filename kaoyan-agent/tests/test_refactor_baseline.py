"""Compare frozen legacy outputs and exact logical model requests after migration."""

import copy
import json
from pathlib import Path

import pytest

from prompts import get
from tests.refactor_cases import execute

CASES = json.loads(
    (Path(__file__).parent / "fixtures/helloagents-baseline.json").read_text()
)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda value: value["case"]["name"])
async def test_frozen_legacy_behavior(case):
    actual = await execute(case["case"])
    # P0 adds provenance to model-visible sources. The historical fixtures stay
    # unchanged; compare their original logical fields and full public results.
    for call in actual["calls"]:
        # 2026-11-03: the new internal advice menu is not a public contract change.
        # This historical case has three attempts and no sources or snapshots.
        if call["schema"] == "LearningAnswer":
            menu = call["payload"].pop("suggestionCandidates")
            assert [row["action"] for row in menu] == ["COLLECT_SAMPLES", "PRACTICE_RELATED"]
            assert all(not row["sourceIds"] and not row["evidenceRefs"] for row in menu)
            assert "本轮区间统计样本不足5次" in menu[0]["text"]
        for key in ("references", "sources"):
            if key in call["payload"]:
                for row in call["payload"][key]:
                    assert row.get("version") and row.get("locator")
                call["payload"][key] = [{"id": row["id"], "content": row["content"]} for row in call["payload"][key]]
        # 2026-11-03: the profile carries an optional degreeType; legacy cases leave it unset.
        if isinstance(call["payload"].get("profile"), dict) and call["payload"]["profile"]:
            assert call["payload"]["profile"].pop("degreeType") is None
    if "profileSnapshot" in actual["result"]:
        assert actual["result"]["profileSnapshot"].pop("degreeType") is None
    expected = copy.deepcopy(case["expected"])
    # 2026-11-03: a missing degree type points to the personal profile first.
    if case["case"]["name"] == "schools_missing":
        expected["result"]["followUp"][-1] = "请在个人档案选择学硕或专硕（也可在本轮说明）"
    # 2026-11-02: unsupported admission prose no longer replaces the rule
    # explanation. The frozen fixture keeps the historical AI result.
    if case["case"]["name"] == "schools_ai":
        expected["result"].update(
            explanationMode="fallback",
            notice="AI解释未能与招生资料原文充分对齐，已保留规则候选说明。",
        )
    # 2026-11-02: downgraded results name a fixed fallbackReason.
    reasons = {"qa_failure": "UNAVAILABLE", "schools_ai": "EVIDENCE_MISMATCH"}
    if case["case"]["name"] in reasons:
        expected["result"]["fallbackReason"] = reasons[case["case"]["name"]]
    # 2026-11-02: the practice summary prompt now asks for only the summary field.
    if case["case"]["name"] == "summary_True":
        expected["calls"][0]["instruction"] = get("practice_summary")
    # 2026-11-02: the learning prompt states each counting basis, and code supplies
    # wrongAttempts so the model never subtracts counts that grounding would reject.
    if case["case"]["name"] == "learning_True":
        expected["calls"][0]["instruction"] = get("learning_expert_0")
        expected["calls"][0]["payload"]["learningContext"]["statistics"]["wrongAttempts"] = 2
    # Trust repair keeps historical fixtures intact, but rejects their legacy
    # free-form learning answer and exposes code-authored wrong-attempt facts.
    for call in expected["calls"]:
        if call["schema"] == "Answer":
            call["instruction"] = get("zhishi_wenda")
    # 2026-11-02: the fixed line no longer says independent attempts are unrecorded,
    # because the rule profile below does count them under its own basis.
    if case["case"]["name"] in {"learning_False", "learning_True"}:
        # 2026-11-03: the concise rule text merges totals into one line.
        rule_answer = ("记录事实：至有效作答3次，正确1次，错误2次，去重题数未记录"
                       "（同题重复作答分别计数；与错题本题数分别统计）。\n"
                       "学习时长与提示辅助未记录。")
        expected["result"]["answer"] = rule_answer
        # 2026-11-03: the notice names the real blocker; this case has the model disabled on the server.
        if case["case"]["name"] == "learning_False":
            expected["result"]["notice"] = "外部模型未在服务端启用，本项使用本地规则。"
        if case["case"]["name"] == "learning_True":
            expected["result"].update(explanationMode="fallback", fallbackReason="INVALID_OUTPUT",
                                      notice="AI分析不可用，已保留本地记录摘要。")
    # 2026-11-02: clarification examples follow the scenario instead of one fixed TCP question.
    if case["case"]["name"] == "clarification":
        expected["result"]["answer"] = ("请说明你指的是哪个知识点或哪份文档。\n"
                                        "推荐问法：请把指代换成具体内容，例如：TCP 拥塞控制中的慢开始是什么意思？")
    if case["case"]["name"] == "document_missing":
        expected["result"]["answer"] = ("请先选择要修改的个人笔记。\n"
                                        "推荐问法：在笔记页选中要修改的笔记后发送：在这份笔记中补充 TCP 拥塞控制的例子。")
    # 2026-11-02: an empty school result names the exam year and the exclusion reasons.
    if case["case"]["name"] == "schools_['广东']":
        expected["result"]["answer"] = ("2027年资料共6个项目，均未满足当前条件。排除原因：地区不匹配6个、专业不匹配3个、"
                                        "学位类型不匹配3个（同一项目可有多项原因）；当前条件为专业081200、学硕，未替换为往年数据。")
    assert actual == expected
