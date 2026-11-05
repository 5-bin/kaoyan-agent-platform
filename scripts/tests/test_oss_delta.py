"""Verify canonical JAR updates preserve every unrelated application/library byte."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC=importlib.util.spec_from_file_location('oss_delta',Path(__file__).resolve().parents[1]/'patch-oss-backend.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)

class OssDeltaTests(unittest.TestCase):
    def test_only_approved_entries_change_and_output_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'old.jar';payload=root/'payload';payload.mkdir()
            data={name:b'old-'+name.encode() for name in m.ALLOWED}
            data['BOOT-INF/classes/ConversationService.class']=b'unchanged business class'
            data['BOOT-INF/lib/example.jar']=b'unchanged dependency'
            with zipfile.ZipFile(source,'w',compression=zipfile.ZIP_DEFLATED) as jar:
                for name,value in data.items():jar.writestr(name,value)
            report={'baseSha256':m.digest(source),'changed':{},'allEntries':{n:hashlib.sha256(v).hexdigest() for n,v in data.items()}}
            for name in m.ALLOWED:
                p=payload/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'new-'+name.encode())
                report['changed'][name]=m.digest(p);report['allEntries'][name]=m.digest(p)
            first=root/'first.jar';second=root/'second.jar'
            m.build(source,payload,first,report);m.build(source,payload,second,report)
            self.assertEqual(m.digest(first),m.digest(second))
            with zipfile.ZipFile(first) as jar:
                self.assertEqual(jar.read('BOOT-INF/classes/ConversationService.class'),data['BOOT-INF/classes/ConversationService.class'])
                self.assertTrue(all(i.compress_type==zipfile.ZIP_STORED for i in jar.infolist()))
            (payload/next(iter(m.ALLOWED))).write_bytes(b'corrupt')
            with self.assertRaises(RuntimeError):m.build(source,payload,root/'invalid.jar',report)
    def test_cli_refuses_live_source_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'live.jar';source.write_bytes(b'keep')
            argv=['patch','--source',str(source),'--output',str(source),'--payload',str(root),'--manifest',str(root/'missing.json'),'--apply']
            with patch.object(sys,'argv',argv),self.assertRaises(RuntimeError):m.main()
            self.assertEqual(source.read_bytes(),b'keep')
