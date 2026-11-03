"""Regression checks for public deployment identity and conflict boundaries."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

SPEC = importlib.util.spec_from_file_location(
    "server_data", Path(__file__).resolve().parents[1] / "prepare-server-data.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def fixture():
    """Return public rows with source IDs that collide with unrelated target IDs."""
    source = {name: [] for name in MODULE.PUBLIC}
    source["school"] = [{"id": 1, "name": "学校甲", "province": "甲省", "level": "211"}]
    source["school_detail"] = [{"id": 2, "school_id": 1, "major_name": "计算机", "major_code": "081200",
                               "year": 2027, "remark": "甲学院，全日制"}]
    source["question"] = [{"id": 1, "subject": "数据结构", "content": "题干", "option_a": "甲",
                          "option_b": "乙", "option_c": "丙", "option_d": "丁", "answer": "A"}]
    source["question_version"] = [{"question_id": 1, "version": 2, "snapshot_json": {"id": 1, "answer": "A"},
                                  "withdrawn": 0, "withdrawal_reason": None}]
    target = {name: [] for name in MODULE.PUBLIC}
    target["school"] = [{"id": 88, "name": "学校甲", "province": "甲省", "level": "普通本科"}]
    target["question"] = [{"id": 1, "subject": "数据结构", "content": "服务器原题", "option_a": "甲",
                          "option_b": "乙", "option_c": "丙", "option_d": "丁", "answer": "B"}]
    return source, target


class ServerDataPlanTests(unittest.TestCase):
    """Protect existing IDs and reject destructive or ambiguous merges."""

    def test_colliding_ids_are_remapped_without_changing_existing_rows(self):
        source, target = fixture()
        original = copy.deepcopy(target)
        plan = MODULE.build_plan(source, target)
        self.assertEqual(target, original)
        self.assertEqual(plan.maps["school"][1], 88)
        self.assertEqual(plan.maps["question"][1], 2)
        self.assertEqual(plan.inserts["school_detail"][0]["school_id"], 88)
        self.assertEqual(plan.inserts["question_version"][0]["snapshot_json"]["id"], 2)
        self.assertEqual(plan.updates, [{"id": 88, "level": "211"}])

    def test_changed_answer_is_a_conflict_instead_of_overwriting_history(self):
        source, target = fixture()
        target["question"] = copy.deepcopy(source["question"])
        target["question"][0]["answer"] = "D"
        with self.assertRaisesRegex(RuntimeError, "禁止覆盖"):
            MODULE.build_plan(source, target)

    def test_reuses_identical_question_under_different_server_id(self):
        source, target = fixture()
        target["question"] = copy.deepcopy(source["question"])
        target["question"][0]["id"] = 91
        plan = MODULE.build_plan(source, target)
        self.assertEqual(plan.maps["question"][1], 91)
        self.assertFalse(plan.inserts["question"])

    def test_rejects_ambiguous_duplicate_questions(self):
        source, target = fixture()
        source["question"].append({**source["question"][0], "id": 100})
        with self.assertRaisesRegex(RuntimeError, "来源存在重复自然键"):
            MODULE.build_plan(source, target)

    def test_rejects_actor_ids_in_source(self):
        source, target = fixture()
        source["question"][0]["reviewer_user_id"] = 33
        with self.assertRaisesRegex(RuntimeError, "审核账号"):
            MODULE.build_plan(source, target)

    def test_same_major_in_different_colleges_remains_separate(self):
        source, target = fixture()
        source["school_detail"].append({**source["school_detail"][0], "id": 3, "remark": "乙学院，全日制"})
        plan = MODULE.build_plan(source, target)
        self.assertEqual(len(plan.inserts["school_detail"]), 2)

    def test_source_text_is_encoded_as_data(self):
        payload = "'); DROP TABLE user; -- $(whoami)"
        encoded = MODULE.literal(payload)
        self.assertNotIn("DROP", encoded)
        self.assertIn(payload.encode().hex(), encoded)
        with self.assertRaises(RuntimeError):
            MODULE.ident("question;DROP TABLE user")

    def test_diagnostic_reports_versions_without_changing_records(self):
        """Expose version drift while retaining the existing fail-closed policy."""
        source, target = fixture()
        source["question"][0]["version"] = 2
        target["question"] = copy.deepcopy(source["question"])
        target["question"][0].update(id=91, version=1)
        original = copy.deepcopy(target)
        report = MODULE.diagnose_rows("question", source["question"], target["question"])
        self.assertEqual(report["changedFields"], {"version": 1})
        self.assertEqual(report["examples"][0]["changes"]["version"], {"server": 1, "local": 2})
        self.assertEqual(target, original)
        with self.assertRaisesRegex(RuntimeError, "禁止覆盖"):
            MODULE.build_plan(source, target)

    def test_diagnostic_caps_public_text_samples_and_ignores_actor_fields(self):
        """Avoid dumping full public documents or any target-side audit identity."""
        source, target = fixture()
        target["question"] = copy.deepcopy(source["question"])
        source["question"][0]["analysis"] = "甲" * 1000
        target["question"][0].update(analysis="乙" * 1000, reviewer_user_id=99)
        report = MODULE.diagnose_rows("question", source["question"], target["question"])
        value = report["examples"][0]["changes"]["analysis"]["server"]
        self.assertEqual(len(value["preview"]), 120)
        self.assertEqual(value["length"], 1000)
        self.assertNotIn("reviewer_user_id", str(report))

    def test_preserves_existing_permission_notice_and_current_snapshot(self):
        """A notice-only difference keeps the target's exact original notice."""
        source, target = fixture()
        source["question"][0].update(version=2, permission_note="本地许可摘要")
        source["question_version"][0]["snapshot_json"].update(version=2, permissionNote="本地许可摘要")
        target["question"] = copy.deepcopy(source["question"])
        target["question"][0].update(id=91, permission_note="服务器完整许可，不应被缩短")
        original = copy.deepcopy(target)
        plan = MODULE.build_plan(source, target)
        self.assertFalse(plan.inserts["question"])
        self.assertEqual(plan.permission_notes[1], "服务器完整许可，不应被缩短")
        self.assertEqual(plan.inserts["question_version"][0]["snapshot_json"]["permissionNote"],
                         "服务器完整许可，不应被缩短")
        self.assertEqual(plan.enriched_snapshots, 1)
        self.assertEqual(target, original)

    def test_notice_difference_does_not_allow_answer_or_version_changes(self):
        """Keep refusing any substantive difference alongside permission metadata."""
        for changed in ({"answer": "D"}, {"version": 3}):
            with self.subTest(changed=changed):
                source, target = fixture()
                source["question"][0].update(version=2, permission_note="摘要")
                target["question"] = copy.deepcopy(source["question"])
                target["question"][0].update(permission_note="完整许可", **changed)
                with self.assertRaisesRegex(RuntimeError, "禁止覆盖"):
                    MODULE.build_plan(source, target)

    def test_older_snapshot_and_existing_snapshot_permissions_stay_immutable(self):
        """Do not replace notices of older or already stored version snapshots."""
        source, target = fixture()
        source["question"][0].update(version=3, permission_note="摘要")
        target["question"] = copy.deepcopy(source["question"])
        target["question"][0]["permission_note"] = "完整许可"
        source["question_version"][0]["snapshot_json"].update(version=2, permissionNote="原历史许可")
        plan = MODULE.build_plan(source, target)
        self.assertEqual(plan.inserts["question_version"][0]["snapshot_json"]["permissionNote"], "原历史许可")
        self.assertEqual(plan.enriched_snapshots, 0)
        target["question_version"] = copy.deepcopy(source["question_version"])
        target["question_version"][0]["snapshot_json"]["permissionNote"] = "服务器历史许可"
        with self.assertRaisesRegex(RuntimeError, "禁止覆盖"):
            MODULE.build_plan(source, target)

    def test_known_2027_remark_labels_reuse_ids_and_keep_original_text(self):
        """Reuse a verified display variant while leaving the target row intact."""
        source, target = fixture()
        source["school_detail"][0]["remark"] = (
            "【官方招生事实】甲学院；全日制；初试408。 来源：https://example.edu；"
            "核验日期：2026-10-24；版本：v1；权限：保留来源。"
        )
        saved = {**source["school_detail"][0], "id": 92, "school_id": 88}
        saved["remark"] = saved["remark"].replace("【官方招生事实】", "【2027官方来源核验摘要】").replace("；核验日期：", "；核验：")
        target["school_detail"] = [saved]
        original = copy.deepcopy(target)
        plan = MODULE.build_plan(source, target)
        self.assertEqual(plan.maps["school_detail"][2], 92)
        self.assertFalse(plan.inserts["school_detail"])
        self.assertEqual(plan.reused["school_detail"], 1)
        self.assertEqual(len(plan.preserved_detail_remarks), 1)
        self.assertEqual(target, original)

    def test_remark_compatibility_does_not_merge_different_colleges_or_sources(self):
        """Keep all qualifiers and source/version text in the identity key."""
        row = {"school_id": 88, "major_name": "计算机", "major_code": "081200", "year": 2027,
               "remark": "【官方招生事实】甲学院；408。 来源：https://a.edu；核验日期：2026-10-24；版本：v1"}
        for before, after in (("甲学院", "乙学院"), ("408", "301"), ("a.edu", "b.edu"), ("v1", "v2"), ("2026-10-24", "2026-10-23")):
            with self.subTest(change=before):
                changed = {**row, "remark": row["remark"].replace(before, after)}
                self.assertNotEqual(MODULE.identity("school_detail", row), MODULE.identity("school_detail", changed))

    def test_remark_compatibility_is_limited_to_observed_year_and_prefix(self):
        """Avoid generalizing a cosmetic alias into other admission years."""
        text = "【2027官方来源核验摘要】甲学院；核验：2026-10-24；版本：v1"
        self.assertEqual(MODULE.detail_remark_key(text, 2026), text)
        self.assertEqual(MODULE.detail_remark_key(text.replace("2027", "2028"), 2028), text.replace("2027", "2028"))
        self.assertEqual(MODULE.detail_remark_key("普通备注；核验：2026-10-24；版本：v1", 2027), "普通备注；核验：2026-10-24；版本：v1")


ROOT = Path(__file__).resolve().parents[2]
BEFORE_V13 = {"practice_record", "task", "question", "user", "chat_conversation", "chat_message", "chat_generation",
              "personal_document", "personal_document_version", "assistant_privacy", "assistant_action"}


class FakeSchema:
    """Answer only the metadata reads used to select migrations."""

    def __init__(self, tables: set[str], user_columns: list[str], has_check: bool):
        self.table_names, self.user_columns, self.has_check = tables, user_columns, has_check

    def tables(self) -> list[str]:
        return sorted(self.table_names)

    def columns(self, table: str) -> list[str]:
        return {"practice_record": ["question_snapshot"], "task": ["deleted_at"], "question": ["permission_note"],
                "user": self.user_columns}.get(table, [])

    def query(self, sql: str) -> str:
        assert "TABLE_CONSTRAINTS" in sql and MODULE.literal("ck_user_degree_type") in sql
        return "1" if self.has_check else "0"


class ServerMigrationTests(unittest.TestCase):
    """2026-11-03: V15 is selected once, after V13/V14, and partial states are refused."""

    def test_selects_v13_v14_and_v15_for_a_v12_database(self):
        db = FakeSchema(set(BEFORE_V13), ["id", "exam_year"], False)
        names = [path.name for path in MODULE.migrations(db, ROOT)]
        self.assertEqual(names, ["V13__learning_loop.sql", "V14__school_admission_metrics.sql",
                                 "V15__profile_degree_type.sql"])
        self.assertTrue(all(path.is_file() for path in MODULE.migrations(db, ROOT)))

    def test_only_v15_is_pending_after_v14(self):
        tables = BEFORE_V13 | set(MODULE.V13) | {"school_admission_metric"}
        names = [path.name for path in MODULE.migrations(FakeSchema(tables, ["id", "exam_year"], False), ROOT)]
        self.assertEqual(names, ["V15__profile_degree_type.sql"])
        self.assertEqual(MODULE.migrations(FakeSchema(tables, ["id", "exam_year", "degree_type"], True), ROOT), [])

    def test_partial_v15_is_refused(self):
        tables = BEFORE_V13 | set(MODULE.V13) | {"school_admission_metric"}
        for columns, check in ((["id", "degree_type"], False), (["id"], True)):
            with self.assertRaisesRegex(RuntimeError, "V15处于部分应用状态"):
                MODULE.migrations(FakeSchema(tables, columns, check), ROOT)

    def test_pre_migration_columns_bound_the_row_hash(self):
        db = MODULE.Database("kaoyan", [], {})
        self.assertEqual(db.expression("user", ["id", "exam_year"]),
                         "SHA2(CAST(JSON_ARRAY(`id`,`exam_year`) AS CHAR),256)")


if __name__ == "__main__":
    unittest.main()
