"""Check exact reversible public guards and preservation of private env lines."""
import importlib.util
from pathlib import Path
import unittest

SPEC=importlib.util.spec_from_file_location('registration_control',Path(__file__).resolve().parents[1]/'registration-control.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)

class RegistrationControlTests(unittest.TestCase):
    def test_guard_roundtrip_preserves_other_nginx_bytes(self):
        original='server {\n    location /api/ { proxy_pass http://127.0.0.1:8080; }\n}\n'
        guarded=m.render_guard(original,True)
        self.assertEqual(m.render_guard(guarded,True),guarded)
        self.assertEqual(m.render_guard(guarded,False),original)
    def test_partial_or_unknown_layout_rejected(self):
        for text in ('unknown','kaoyan-test-registration-guard'):
            with self.assertRaises(RuntimeError):m.render_guard(text,True)
    def test_env_flag_only_changes_registration(self):
        for original in ('OTHER=synthetic\n','OTHER=synthetic\nREGISTRATION_ENABLED=true\n'):
            closed=m.close_flag(original)
            self.assertIn('OTHER=synthetic\n',closed)
            self.assertIn('REGISTRATION_ENABLED=false',closed)
            self.assertEqual(m.close_flag(closed),closed)
        with self.assertRaises(RuntimeError):m.close_flag('REGISTRATION_ENABLED=true\nREGISTRATION_ENABLED=false')
