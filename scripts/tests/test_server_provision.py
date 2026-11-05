"""Check synthetic distribution, read-only defaults and uncertain-create recovery."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SPEC=importlib.util.spec_from_file_location('server_provision',Path(__file__).resolve().parents[1]/'provision-server-test-accounts.py')
m=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=m;SPEC.loader.exec_module(m)


class ProvisionTests(unittest.TestCase):
    def test_all_accounts_have_exact_subject_and_total_counts(self):
        for account in range(1,11):
            totals=[]
            for subject in range(4):
                actual=0
                for week in range(5):
                    q=m.Question(1,m.SUBJECTS[subject],'point','EASY','A',1)
                    count=sum(m.planned_answer(q,account,subject,week,i)=='A' for i in range(20))
                    self.assertEqual(count,m.correct_per_round(account,subject,week))
                    actual+=count
                totals.append(actual)
            weak=(account-1)%4
            self.assertEqual(totals[weak],30+10*((account-1)//4))
            self.assertEqual(sorted(totals),sorted([30+10*((account-1)//4),60,70,80]))

    def test_question_selection_covers_four_subjects_and_three_difficulties(self):
        rows=[]
        for subject in m.SUBJECTS:
            for i in range(24):
                rows.append(dict(id=len(rows)+1,subject=subject,point='point'+str(i%4),difficulty=('EASY','MEDIUM','HARD')[i%3],answer='A',version=1))
        selected=m.select_questions(rows)
        self.assertEqual(len(selected),80)
        for subject in m.SUBJECTS:
            group=[q for q in selected if q.subject==subject]
            self.assertEqual(len(group),20)
            self.assertEqual({q.difficulty for q in group},{'EASY','MEDIUM','HARD'})
        with self.assertRaises(RuntimeError):m.select_questions(rows[:10])

    def test_existing_name_refuses_before_backup_or_directory_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            obj=m.Provisioner(Mock(),Mock(),root,root/'new',{n:'synthetic' for n in m.NAMES})
            try:
                with patch.object(obj,'preview',return_value={'occupiedNames':['test1']}):
                    with self.assertRaises(RuntimeError):obj.prepare()
                self.assertFalse(obj.output.exists())
                obj.helper.rehearse.assert_not_called()
            finally:obj.close()

    def test_uncertain_session_creation_adopts_one_matching_batch_without_post(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);obj=m.Provisioner(Mock(),Mock(),root,root,{})
            obj.state={'accounts':{'test1':{'ownerId':7,'sessions':{'0:0':{'id':None,'before':['old']}}}}}
            group=[m.Question(i,'数据结构','point','EASY','A',1) for i in range(20)]
            obj.db.query.return_value='old\ncreated-before-crash'
            try:
                with patch.object(obj,'api',return_value={'items':[{'questionId':q.id} for q in group]}) as api:
                    self.assertEqual(obj.session('test1','private',0,0,group),'created-before-crash')
                    self.assertEqual(api.call_args.args[0],'GET')
            finally:obj.close()

    def test_ambiguous_sessions_never_create_another_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);obj=m.Provisioner(Mock(),Mock(),root,root,{})
            obj.state={'accounts':{'test1':{'ownerId':7,'sessions':{'0:0':{'id':None,'before':[]}}}}}
            obj.db.query.return_value='one\ntwo'
            try:
                with patch.object(obj,'api') as api:
                    with self.assertRaises(RuntimeError):obj.session('test1','private',0,0,[])
                    api.assert_not_called()
            finally:obj.close()

    def test_private_progress_has_no_group_or_world_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'progress.json';m.save(path,{'ownerId':7})
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertEqual(json.loads(path.read_text()),{'ownerId':7})

    def test_history_refuses_unjournaled_session_before_any_update(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);obj=m.Provisioner(Mock(),Mock(),root,root,{})
            obj.state={'accounts':{'test1':{'ownerId':7,'sessions':{str(i):{'id':str(i)} for i in range(20)}}}}
            obj.db.query.return_value='unexpected-session'
            try:
                with self.assertRaises(RuntimeError):obj.project('test1')
                self.assertEqual(len(obj.db.query.call_args_list),1)
                self.assertTrue(obj.db.query.call_args.args[0].startswith('SELECT'))
            finally:obj.close()


if __name__=='__main__':unittest.main()
