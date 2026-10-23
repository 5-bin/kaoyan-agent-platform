"""Independent examples and corruption checks for data used in real MySQL."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from feature_fixture import all_questions,oracle,validate_questions
from feature_env import Database,DATABASE,sql


class FixtureChecks(unittest.TestCase):
    def test_numeric_examples(self):
        # Golden values reasoned independently from the authored answer strings.
        self.assertEqual(oracle('fifo',[[1,2,3,4,1,2,5,1,2,3,4,5],3]),9)
        self.assertEqual(oracle('fifo',[[1,2,3,4,1,2,5,1,2,3,4,5],4]),10)
        self.assertEqual(oracle('huffman',[2,3,7,9]),38)
        self.assertEqual(oracle('signed',[246,8]),-10)
        self.assertEqual(oracle('hosts',[26]),62)
        self.assertAlmostEqual(oracle('speedup',[.8,4]),2.5)

    def test_unknown_verification_is_data_not_code(self):
        with self.assertRaises(ValueError): oracle('__import__("os")',[])

    def test_altered_numeric_answer_is_rejected(self):
        qs=all_questions();q=next(q for q in qs if q.get('verification'))
        q['answer']='ABCD'[('ABCD'.index(q['answer'])+1)%4]
        with self.assertRaises(ValueError): validate_questions(qs)

    def test_multi_letter_answer_is_rejected(self):
        qs=all_questions();qs[0]['answer']='AB'
        with self.assertRaises(ValueError): validate_questions(qs)

    def test_duplicate_question_is_rejected(self):
        qs=all_questions();qs[1]['code']=qs[0]['code']
        with self.assertRaises(ValueError): validate_questions(qs)

    def test_remote_database_rejected_before_execution(self):
        with self.assertRaises(RuntimeError): Database(dict(DB_HOST='remote.example'))

    def test_sql_quotes_are_not_executable(self):
        value="x'; DROP DATABASE example; --"
        encoded=sql(value)
        self.assertNotIn('DROP',encoded)
        self.assertEqual(bytes.fromhex(encoded.split("'")[1]).decode(),value)

    def test_checked_fixture_matches_authoring_source(self):
        stored=json.loads((ROOT/'scripts/fixtures/feature-2027-questions.json').read_text())
        self.assertEqual(stored,all_questions())


if __name__=='__main__': unittest.main()
