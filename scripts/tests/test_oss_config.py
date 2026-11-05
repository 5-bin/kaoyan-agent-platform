"""Validate OSS-only environment updates without production access."""
import importlib.util
from io import StringIO
from pathlib import Path
import unittest
import tempfile
import os
import sys
from unittest.mock import patch
from dotenv import dotenv_values

SPEC=importlib.util.spec_from_file_location('oss_config',Path(__file__).resolve().parents[1]/'configure-server-oss.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)

class OssConfigTests(unittest.TestCase):
    def values(self):
        return dict(OSS_ENDPOINT='https://oss-cn-shenzhen.aliyuncs.com',OSS_BUCKET_NAME='example-bucket',OSS_ACCESS_KEY_ID='synthetic',OSS_ACCESS_KEY_SECRET='synthetic+secret/=',OSS_URL_PREFIX='',OSS_KEY_PREFIX='prod/')
    def test_only_oss_keys_change_and_secrets_roundtrip(self):
        original='REGISTRATION_ENABLED=false\nLLM_ENABLED=false\nDB_PASSWORD=synthetic-db\nOSS_ENDPOINT=\n'
        result=m.merge(original,self.values());parsed=dotenv_values(stream=StringIO(result))
        for k,v in self.values().items():self.assertEqual(parsed[k],v)
        self.assertIn('DB_PASSWORD=synthetic-db\n',result)
        self.assertEqual(m.merge(result,self.values()),result)
    def test_invalid_endpoint_prefix_duplicates_or_newline_rejected(self):
        for key,value in [('OSS_ENDPOINT','http://evil.test'),('OSS_KEY_PREFIX','../local'),('OSS_ACCESS_KEY_SECRET','bad\nsecret'),('OSS_URL_PREFIX','https://other')]:
            values=self.values();values[key]=value
            with self.assertRaises(RuntimeError):m.merge('',values)
        with self.assertRaises(RuntimeError):m.merge('OSS_ENDPOINT=\nOSS_ENDPOINT=\n',self.values())

    def test_real_file_apply_restore_idempotence_and_concurrent_change_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            env=root/'server.env';original='LLM_ENABLED=false\nREGISTRATION_ENABLED=false\nDB_NAME=synthetic_db\n'
            env.write_text(original);env.chmod(0o640)
            config=root/'config.json';config.write_text(__import__('json').dumps(self.values()));config.chmod(0o600)
            output=root/'backup'
            argv=['configure','--config',str(config),'--output',str(output)]
            real_path=Path
            previous_umask=os.umask(0o077)
            try:
                with patch.object(m,'ENV',env),patch.object(m,'Path',side_effect=lambda p:root if str(p)=='/root' else real_path(p)),patch.object(m.socket,'gethostname',return_value='iZj6cb4euf28b560hanyr7Z'),patch.object(m.os,'geteuid',return_value=0),patch.object(m,'avatars',return_value=0):
                    with patch.object(sys,'argv',argv):m.main()
                    self.assertEqual(env.read_text(),original);self.assertFalse(output.exists())
                    with patch.object(sys,'argv',argv+['--apply']):m.main()
                    applied=env.read_text();self.assertNotEqual(applied,original)
                    self.assertEqual(env.stat().st_mode&0o777,0o640)
                    self.assertEqual((output/'env.before').stat().st_mode&0o777,0o600)
                    env.write_text(applied+'CONCURRENT_CHANGE=keep\n')
                    restore=['configure','--output',str(output),'--restore','--apply']
                    with patch.object(sys,'argv',restore),self.assertRaises(RuntimeError):m.main()
                    self.assertIn('CONCURRENT_CHANGE=keep',env.read_text())
                    env.write_text(applied)
                    with patch.object(sys,'argv',restore):m.main()
                    self.assertEqual(env.read_text(),original)
                    with patch.object(sys,'argv',restore):m.main()
                    self.assertEqual(env.read_text(),original)
            finally:os.umask(previous_umask)
