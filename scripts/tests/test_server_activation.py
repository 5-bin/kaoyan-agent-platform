"""Check maintenance ordering and bounded program rollback without real systemd."""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location(
    "server_activation", Path(__file__).resolve().parents[1] / "activate-server-release.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

NGINX = """server {
    listen 80;
    server_name 47.83.150.142;
    root /opt/kaoyan/kaoyan-frontend/dist;
    location ^~ /.well-known/acme-challenge/ { try_files $uri =404; }
    location / { return 301 https://47.83.150.142$request_uri; }
}
server {
    listen 443 ssl;
    root /opt/kaoyan/kaoyan-frontend/dist;
    ssl_certificate /etc/letsencrypt/live/kaoyan-ip/fullchain.pem;
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_buffering off;
    }
}
"""


class ServerActivationTests(unittest.TestCase):
    """Protect the API maintenance window, old configuration and committed data."""

    def activation(self, root: Path) -> MODULE.Activation:
        """Build an inert activation object whose external operations are mocked."""
        return MODULE.Activation(root / "release", root / "rehearsal", root / "helper.py",
                                 "expected-plan", root / "output", True, True, Mock())

    def test_nginx_switch_preserves_http_challenge_and_certificate(self) -> None:
        """Only the HTTPS static root changes; API gates disappear after readiness."""
        release = Path("/opt/kaoyan-releases/test-release")
        old_gate, new_gate, final = MODULE.nginx_versions(NGINX, release)
        self.assertEqual(old_gate.count("return 503;"), 1)
        self.assertEqual(new_gate.count("return 503;"), 1)
        self.assertNotIn("return 503;", final)
        self.assertIn("root /opt/kaoyan/kaoyan-frontend/dist;", final.split("listen 443")[0])
        self.assertIn(str(release / "kaoyan-frontend/dist"), final.split("listen 443")[1])
        self.assertIn("ssl_certificate /etc/letsencrypt/live/kaoyan-ip/fullchain.pem;", final)
        self.assertIn("proxy_buffering off;", final)

    def test_unknown_nginx_layout_is_rejected(self) -> None:
        """Never guess which site block to replace if the known layout changes."""
        with self.assertRaises(RuntimeError):
            MODULE.nginx_versions(NGINX.replace("root /opt/kaoyan/kaoyan-frontend/dist;", "root /another/site;", 1), Path("/tmp/release"))

    def test_dropins_keep_private_bindings_and_do_not_enable_models(self) -> None:
        """Feature flags never copy keys or enable model calls."""
        cache = {"QUESTION_INDEX": Path("/opt/kaoyan/kaoyan-agent/.cache/questions")}
        configs = MODULE.dropins(Path("/opt/kaoyan-releases/test"), cache, True, True)
        self.assertIn("--host 127.0.0.1 --port 8001 --workers 1", configs[MODULE.SERVICES[0]])
        self.assertIn("--server.address=127.0.0.1", configs[MODULE.SERVICES[1]])
        self.assertIn("Environment=KAOYAN_LEARNING_ENABLED=true", configs[MODULE.SERVICES[1]])
        self.assertIn("Environment=ADMISSION_MCP_ENABLED=true", configs[MODULE.SERVICES[0]])
        for text in configs.values():
            self.assertNotIn("LLM_ENABLED", text)
            self.assertNotIn("API_KEY", text)
            self.assertNotIn("DB_PASSWORD", text)

    def test_failed_data_stage_rolls_back_before_any_new_service_starts(self) -> None:
        """A failed backup or data check must not proceed to code publication."""
        events = []
        def fail() -> None:
            events.append("data")
            raise RuntimeError("backup failed")
        with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            MODULE.run_switch([
                ("gate", lambda: events.append("gate")),
                ("stop", lambda: events.append("stop")),
                ("data", fail),
                ("start", lambda: events.append("start")),
            ], lambda: events.append("rollback"))
        self.assertEqual(events, ["gate", "stop", "data", "rollback"])

    def test_failed_gate_never_reaches_the_database_stage(self) -> None:
        """Prevent database writes unless the API maintenance gate succeeded."""
        data = Mock()
        rollback = Mock()
        with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            MODULE.run_switch([("gate", Mock(side_effect=RuntimeError("gate failed"))), ("data", data)], rollback)
        data.assert_not_called()
        rollback.assert_called_once()

    def test_changed_plan_stops_before_backup_and_schema_changes(self) -> None:
        """Bind production SQL to the reviewed hash after stopping old writers."""
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            obj = self.activation(root)
            obj.output.mkdir()
            obj.db = Mock()
            obj.helper = SimpleNamespace(inspect=Mock(return_value=(Mock(), [])),
                                         summary=Mock(return_value={"planSha256": "changed"}), rehearse=Mock())
            with self.assertRaisesRegex(RuntimeError, "未执行写入"):
                obj.data()
            obj.helper.rehearse.assert_not_called()
            obj.db.query.assert_not_called()

    def test_program_rollback_keeps_committed_business_data(self) -> None:
        """Rollback removes only this operation's drop-ins and never issues SQL."""
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            obj = self.activation(root)
            obj.db = Mock()
            obj.state.update(siteTouched=True, servicesTouched=True, dataCommitConfirmed=True)
            obj.candidates = ("maintenance", "new-maintenance", "new")
            obj.original = b"old-site"
            obj.overrides = {service: service + " new config" for service in MODULE.SERVICES}
            files = {service: root / (service + ".conf") for service in MODULE.SERVICES}
            for service, path in files.items():
                path.write_text(obj.overrides[service])
            obj.written_dropins = list(MODULE.SERVICES)
            other = root / "unrelated.conf"
            other.write_text("keep existing administrator config")
            with patch.object(obj, "drop_path", side_effect=files.__getitem__), patch.object(obj, "nginx") as nginx, patch.object(obj, "ready"):
                obj.rollback()
                self.assertEqual([call.args[0] for call in nginx.call_args_list], ["maintenance", "old-site"])
            obj.db.query.assert_not_called()
            self.assertTrue(obj.state["dataCommitConfirmed"])
            self.assertTrue(obj.state["oldProgramRestored"])
            self.assertEqual(other.read_text(), "keep existing administrator config")
            self.assertTrue(all(not path.exists() for path in files.values()))

    def test_failed_rollback_start_keeps_api_in_maintenance(self) -> None:
        """Do not reopen the public API if the old services cannot recover."""
        with tempfile.TemporaryDirectory() as name:
            obj = self.activation(Path(name))
            obj.state.update(siteTouched=True, servicesTouched=True)
            obj.candidates = ("maintenance", "new-maintenance", "new")
            obj.original = b"old-site"
            def command(args: list[str]) -> str:
                if args[:2] == ["systemctl", "start"]:
                    raise RuntimeError("start failed")
                return ""
            obj.system.command.side_effect = command
            with patch.object(obj, "nginx") as nginx, self.assertRaises(RuntimeError):
                obj.rollback()
            nginx.assert_called_once_with("maintenance")
            self.assertNotIn("oldProgramRestored", obj.state)

    def test_default_cli_is_check_only(self) -> None:
        """Loading and checking the tool never starts an update implicitly."""
        argv = ["activate-server-release.py", "--release-root", "/opt/kaoyan-releases/test",
                "--rehearsal", "/root/test-rehearsal", "--expected-plan", "hash", "--output", "/root/test-output"]
        with patch.object(sys, "argv", argv), patch.object(MODULE, "Activation") as cls, redirect_stdout(io.StringIO()):
            cls.return_value.validate.return_value = {"checked": True}
            MODULE.main()
            cls.return_value.activate.assert_not_called()

    def test_loopback_probe_refuses_external_targets(self) -> None:
        """An unverified TLS context must never be used against a public endpoint."""
        with self.assertRaises(RuntimeError):
            MODULE.System(Path("/tmp/no-output")).http("https://47.83.150.142/")

    def test_probe_does_not_follow_a_redirect_from_loopback(self) -> None:
        """Never carry the loopback probe's TLS policy to a redirect destination."""
        class Redirect(BaseHTTPRequestHandler):
            """Serve an isolated redirect fixture without external requests."""

            def do_GET(self) -> None:
                """Point outside loopback; the probe must return 302 directly."""
                self.send_response(302)
                self.send_header("Location", "https://example.invalid/")
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                """Keep the local fixture from printing routine request logs."""
                return None

        with ThreadingHTTPServer(("127.0.0.1", 0), Redirect) as server:
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                status, _ = MODULE.System(Path("/tmp/no-output")).http(
                    "http://127.0.0.1:" + str(server.server_port) + "/"
                )
                self.assertEqual(status, 302)
            finally:
                server.shutdown()
                worker.join(timeout=2)

    def test_backend_readiness_uses_protected_get_and_requires_401(self) -> None:
        """A GET on a POST-only login endpoint is not a valid health probe."""
        with tempfile.TemporaryDirectory() as name:
            obj = self.activation(Path(name))
            seen = []
            def http(url: str) -> tuple[int, bytes]:
                seen.append(url)
                if url.endswith("/health"):
                    return 200, b'{"status":"ok"}'
                return 401, b'{}'
            obj.system.http.side_effect = http
            obj.system.wait_for.side_effect = lambda check, message, **kwargs: self.assertTrue(check())
            obj.system.command.return_value = "active"
            obj.ready(new=False)
            self.assertIn("http://127.0.0.1:8080/api/_deployment_probe", seen)
            self.assertFalse(any(url.endswith("/api/auth/login") for url in seen))

    def test_previously_committed_data_is_rechecked_without_production_sql(self) -> None:
        """Fresh backup rehearsal may run, but no migration or merge hits the live DB."""
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            obj = self.activation(root)
            obj.output.mkdir()
            obj.committed_activation = root / "prior"
            obj.current_plan_sha = "current"
            obj.source = {"question": [{"id": 1}]}
            plan = SimpleNamespace(inserts={"question": []}, updates=[])
            obj.helper = SimpleNamespace(
                inspect=Mock(return_value=(plan, [])),
                summary=Mock(return_value={"planSha256": "current"}),
                rehearse=Mock(), PUBLIC=("question",), ident=lambda table: "`" + table + "`",
            )
            obj.db = Mock()
            obj.db.query.return_value = "1"
            obj.data()
            self.assertTrue(obj.state["dataAlreadyCommitted"])
            self.assertTrue(obj.state["dataCommitConfirmed"])
            self.assertEqual(obj.db.query.call_count, 1)
            self.assertTrue(obj.db.query.call_args.args[0].startswith("SELECT COUNT"))

    def test_changed_committed_data_stops_before_backup(self) -> None:
        """Do not reuse a prior commit if the current public plan has changed."""
        with tempfile.TemporaryDirectory() as name:
            obj = self.activation(Path(name))
            obj.output.mkdir()
            obj.committed_activation = Path(name) / "prior"
            obj.current_plan_sha = "reviewed-current"
            obj.db = Mock()
            obj.helper = SimpleNamespace(inspect=Mock(return_value=(Mock(), [])),
                                         summary=Mock(return_value={"planSha256": "changed"}), rehearse=Mock())
            with self.assertRaisesRegex(RuntimeError, "未执行写入"):
                obj.data()
            obj.helper.rehearse.assert_not_called()
            obj.db.query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
