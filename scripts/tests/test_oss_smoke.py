"""Check guarded avatar restoration and env-before-program rollback ordering."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import oss_smoke as smoke
SPEC=importlib.util.spec_from_file_location('oss_release',Path(__file__).resolve().parents[1]/'activate-oss-release.py')
m=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=m;SPEC.loader.exec_module(m)

class OssSmokeTests(unittest.TestCase):
    def receipt(self):
        key='prod/avatar/8/20261103/abc123.png'
        return {'ownerId':8,'objectKey':key,'url':'https://example.oss-cn-shenzhen.aliyuncs.com/'+key}
    def test_cleanup_guards_exact_user_and_url_before_delete(self):
        receipt=self.receipt();db=Mock()
        with patch.object(smoke,'api',side_effect=[{'id':8,'username':'test1','avatarUrl':receipt['url']},{'avatarUrl':None},None]) as api:
            smoke.cleanup(Mock(),db,'private-token',receipt)
        sql=db.query.call_args.args[0]
        self.assertIn("username='test1'",sql)
        self.assertIn('id=8',sql)
        self.assertIn('AND avatar_url=CONVERT(0x',sql)
        self.assertEqual(api.call_args.args[1],'DELETE')
        self.assertTrue(receipt['testObjectDeleted'])
    def test_cleanup_never_overwrites_concurrent_or_foreign_avatar(self):
        for me in ({'id':9,'username':'test2','avatarUrl':None},{'id':8,'username':'test1','avatarUrl':'another-avatar'}):
            db=Mock()
            with patch.object(smoke,'api',return_value=me) as api:
                with self.assertRaises(RuntimeError):smoke.cleanup(Mock(),db,'private-token',self.receipt())
                db.query.assert_not_called();self.assertEqual(api.call_count,1)
    def test_rollback_restores_env_before_old_program_start(self):
        obj=m.OssUpgrade(Mock(),Mock(),Mock(),'plan',Mock(),False,False,Mock())
        events=[]
        with patch.object(obj,'restore_environment',side_effect=lambda:events.append('env')),patch.object(m.upgrade.Upgrade,'rollback',side_effect=lambda:events.append('program')):
            obj.rollback()
        self.assertEqual(events,['env','program'])
    def test_failed_env_restore_never_starts_old_program_with_new_oss_settings(self):
        obj=m.OssUpgrade(Mock(),Mock(),Mock(),'plan',Mock(),False,False,Mock())
        with patch.object(obj,'restore_environment',side_effect=RuntimeError('env changed')),patch.object(m.upgrade.Upgrade,'rollback') as rollback:
            with self.assertRaises(RuntimeError):obj.rollback()
            rollback.assert_not_called()
