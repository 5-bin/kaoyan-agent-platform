"""Exercise V15-only data writes, exact rollback and trusted runtime manifests."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location("server_upgrade", Path(__file__).resolve().parents[1] / "upgrade-server-release.py")
m = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = m
SPEC.loader.exec_module(m)

CURRENT = Path("/opt/kaoyan-releases/kaoyan-release-old")
RELEASE = Path("/opt/kaoyan-releases/kaoyan-release-new")
NGINX = """server { listen 80; root /opt/kaoyan/kaoyan-frontend/dist;
location ^~ /.well-known/acme-challenge/ { try_files $uri =404; }}
server { listen 443 ssl;
ssl_certificate /keep/cert;
root /opt/kaoyan-releases/kaoyan-release-old/kaoyan-frontend/dist;
location /api/ { proxy_pass http://127.0.0.1:8080; }}
"""


class UpgradeTests(unittest.TestCase):
    """Verify production safety boundaries without touching running services."""

    def obj(self, root: Path) -> m.Upgrade:
        """Build an inert object for data and config failure injection."""
        result = m.Upgrade(root / "release", root / "rehearsal", root / "helper", "plan", root / "output", False, False, Mock())
        result.output.mkdir()
        result.db = Mock()
        result.helper = Mock()
        result.helper.summary.return_value = {"planSha256": "plan"}
        def rehearse(db, source, release, directory, report):
            report["rehearsal"] = {"backupSha256": "backup"}
        result.helper.rehearse.side_effect = rehearse
        result.db.tables.return_value = ["user", "question"]
        result.db.columns.side_effect = lambda table: ["id", "username"] if table == "user" else ["id", "answer"]
        result.db.fingerprints.return_value = {"user": ["hash"], "question": ["qhash"]}
        result.db.query.return_value = "0"
        return result

    def test_nginx_preserves_http_and_certificates(self) -> None:
        old, gated, final = m.upgrade_nginx(NGINX, CURRENT, RELEASE)
        self.assertEqual(old.count("return 503;"), 1)
        self.assertEqual(gated.count("return 503;"), 1)
        self.assertNotIn("return 503;", final)
        self.assertIn("root /opt/kaoyan/kaoyan-frontend/dist;", final)
        self.assertIn("ssl_certificate /keep/cert;", final)
        self.assertIn(str(RELEASE / "kaoyan-frontend/dist"), final)

    def test_unknown_or_maintained_site_rejected(self) -> None:
        for text in (NGINX.replace(str(CURRENT), "/other"), NGINX + "return 503;"):
            with self.assertRaises(RuntimeError):
                m.upgrade_nginx(text, CURRENT, RELEASE)

    def test_dropin_preserves_all_nonpath_settings(self) -> None:
        old = "[Service]\nWorkingDirectory=" + str(CURRENT / "kaoyan-agent") + "\nExecStart=" + str(CURRENT / ".venv/bin/python") + " -m uvicorn main:create_app\nEnvironment=ADMISSION_MCP_ENABLED=true\nEnvironment=QUESTION_INDEX=/opt/kaoyan/shared\n"
        new = m.replace_dropin(old, CURRENT, RELEASE, m.base.SERVICES[0])
        self.assertEqual(new.replace(str(RELEASE), str(CURRENT)), old)
        with self.assertRaises(RuntimeError):
            m.replace_dropin(old + "# extra " + str(CURRENT), CURRENT, RELEASE, m.base.SERVICES[0])

    def test_manifest_rejects_missing_extra_tampered_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "release"
            jar = root / "kaoyan-B/target/kaoyan-backend-1.0.0.jar"
            jar.parent.mkdir(parents=True)
            jar.write_bytes(b"trusted jar")
            manifest = Path(name) / "manifest.json"
            manifest.write_text(json.dumps({str(jar.relative_to(root)): m.base.sha(jar)}))
            expected = m.base.sha(manifest)
            m.verify_manifest(root, manifest, expected)
            jar.write_bytes(b"changed")
            with self.assertRaises(RuntimeError):
                m.verify_manifest(root, manifest, expected)
            jar.write_bytes(b"trusted jar")
            extra = root / "kaoyan-agent/extra.py"
            extra.parent.mkdir()
            extra.write_text("extra")
            with self.assertRaises(RuntimeError):
                m.verify_manifest(root, manifest, expected)
            extra.unlink()
            jar.unlink()
            jar.symlink_to(manifest)
            with self.assertRaises(RuntimeError):
                m.verify_manifest(root, manifest, expected)

    def test_v15_checks_exact_column_and_enforced_allowed_values(self) -> None:
        db = Mock()
        db.query.side_effect = ["varchar:16:YES:NULL", "((`degree_type` is null) or (`degree_type` in (_utf8mb4'academic',_utf8mb4'professional')))"]
        m.validate_v15(db)
        db.query.side_effect = ["varchar:16:YES:NULL", r"((`degree_type` is null) or (`degree_type` in (_utf8mb4\'academic\',_utf8mb4\'professional\')))"]
        m.validate_v15(db)
        for column, check in (("varchar:32:YES:NULL", ""), ("varchar:16:YES:NULL", ""), ("varchar:16:YES:NULL", "degree_type IN ('academic','other')")):
            db.query.side_effect = [column, check]
            with self.assertRaises(RuntimeError):
                m.validate_v15(db)

    def test_no_public_writes_or_other_migrations_allowed(self) -> None:
        obj = m.Upgrade(Mock(), Mock(), Mock(), "plan", Mock(), False, False, Mock())
        for plan, pending in ((Mock(inserts={"school": [1]}, updates=[]), []), (Mock(inserts={}, updates=[1]), []), (Mock(inserts={}, updates=[]), [Path("V14.sql")])):
            with self.assertRaises(RuntimeError):
                obj.check_plan(plan, pending)

    def test_v15_data_preserves_preexisting_columns_and_writes_only_v15(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            obj = self.obj(Path(name))
            sql = Path(name) / m.V15_NAME
            sql.write_text("approved V15 SQL")
            obj.helper.inspect.return_value = (Mock(inserts={}, updates=[]), [sql])
            with patch.object(m, "V15_SHA", m.base.sha(sql)), patch.object(m, "validate_v15"):
                obj.data()
            sql_calls = [call.args[0] for call in obj.db.query.call_args_list]
            self.assertEqual(sql_calls, ["approved V15 SQL", "SELECT COUNT(*) FROM `user` WHERE degree_type IS NOT NULL;"])
            self.assertEqual(obj.db.fingerprints.call_args_list[0], obj.db.fingerprints.call_args_list[1])
            self.assertEqual(obj.db.fingerprints.call_args.args[1]["user"], ["id", "username"])
            self.assertTrue(obj.state["originalRowsPreserved"])

    def test_existing_v15_skips_all_production_sql(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            obj = self.obj(Path(name))
            obj.helper.inspect.return_value = (Mock(inserts={}, updates=[]), [])
            with patch.object(m, "validate_v15"):
                obj.data()
            obj.db.query.assert_not_called()
            self.assertFalse(obj.state["schemaApplied"])

    def test_changed_plan_or_backup_failure_never_runs_sql(self) -> None:
        for stage in ("plan", "backup"):
            with tempfile.TemporaryDirectory() as name:
                obj = self.obj(Path(name))
                obj.helper.inspect.return_value = (Mock(inserts={}, updates=[]), [Path(m.V15_NAME)])
                if stage == "plan":
                    obj.helper.summary.return_value = {"planSha256": "different"}
                else:
                    obj.helper.rehearse.side_effect = RuntimeError("restore failed")
                with self.assertRaises(RuntimeError):
                    obj.data()
                obj.db.query.assert_not_called()

    def test_default_cli_never_activates_or_takes_execution_lock(self) -> None:
        """Read-only checks cannot stop services or enter migration execution."""
        argv = ["upgrade"]
        for name in ("current-release", "release-root", "rehearsal", "data-helper", "manifest", "output"):
            argv += ["--" + name, "/tmp/" + name]
        argv += ["--expected-plan", "plan", "--expected-manifest", "manifest"]
        with patch.object(sys, "argv", argv), patch.object(m, "Upgrade") as factory, patch.object(m, "deployment_lock") as lock:
            factory.return_value.validate.return_value = {"readonly": True}
            m.main()
            factory.return_value.validate.assert_called_once()
            factory.return_value.activate.assert_not_called()
            lock.assert_not_called()

    def test_changed_service_config_is_not_overwritten(self) -> None:
        """Check every preimage before writing any service configuration."""
        with tempfile.TemporaryDirectory() as name:
            obj = self.obj(Path(name))
            paths = {}
            for service in m.base.SERVICES:
                path = Path(name) / service
                path.write_bytes(b"original")
                paths[service] = path
                obj.original_dropins[service] = b"original"
            paths[m.base.SERVICES[1]].write_bytes(b"concurrent admin change")
            with patch.object(m, "verify_manifest"), patch.object(obj, "drop_path", side_effect=paths.__getitem__), patch.object(obj, "restore") as write:
                with self.assertRaises(RuntimeError):
                    obj.install()
                write.assert_not_called()
            self.assertEqual(paths[m.base.SERVICES[1]].read_bytes(), b"concurrent admin change")

    def test_concurrent_lock_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "lock"
            with m.deployment_lock(path):
                with self.assertRaises(RuntimeError):
                    with m.deployment_lock(path):
                        self.fail("second process entered")
            with m.deployment_lock(path):
                pass

    def test_rollback_restores_exact_existing_configs(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            obj = self.obj(Path(name))
            paths = {}
            for service in m.base.SERVICES:
                path = Path(name) / service
                path.write_text("new " + service)
                paths[service] = path
                obj.remember(path)
                obj.overrides[service] = path.read_text()
                obj.original_dropins[service] = ("original " + service).encode()
            obj.written_dropins = list(paths)
            obj.state.update(siteTouched=True, servicesTouched=True, v15Verified=True)
            obj.site = Path(name) / "site"
            obj.site.write_text("new gate")
            obj.original = b"original site"
            obj.candidates = ("old gate", "new gate", "new site")
            with patch.object(obj, "drop_path", side_effect=paths.__getitem__), patch.object(obj, "nginx") as nginx, patch.object(obj, "ready"), patch.object(os, "chown"):
                obj.rollback()
            self.assertEqual([c.args[0] for c in nginx.call_args_list], ["old gate", "original site"])
            self.assertTrue(all(path.read_bytes() == obj.original_dropins[s] for s, path in paths.items()))
            obj.db.query.assert_not_called()
            self.assertTrue(obj.state["v15Verified"])

    def test_failed_old_service_keeps_api_gated(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            obj = self.obj(Path(name))
            obj.state.update(siteTouched=True, servicesTouched=True)
            obj.site = Path(name) / "site"
            obj.site.write_text("new gate")
            obj.original = b"old site"
            obj.candidates = ("old gate", "new gate", "new site")
            with patch.object(obj, "nginx") as nginx, patch.object(obj, "ready", side_effect=RuntimeError("old service failed")):
                with self.assertRaises(RuntimeError):
                    obj.rollback()
            self.assertEqual([c.args[0] for c in nginx.call_args_list], ["old gate"])
            self.assertNotIn("oldProgramRestored", obj.state)


if __name__ == "__main__":
    unittest.main()
