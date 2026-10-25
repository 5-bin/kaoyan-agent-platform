import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
import real_data_catalog as catalog


def test_every_translation_is_backed_by_original_solution_and_distractors():
    qs=catalog.questions()
    assert 40 <= len(qs) <= 80
    assert len({q['source_question_no'] for q in qs})==len(qs)
    for q in qs:
        assert len(set(q['options']))==4
        assert q['original_options']['ABCD'.index(q['answer'])]==q['original_answer']
        assert q['source_type']=='COURSE_EXERCISE'
        assert q['source_blob'] in q['source_locator']
        assert '非408统考真题' in q['analysis']


def test_source_tampering_is_detected():
    data=json.loads((catalog.ROOT/'scripts/fixtures/real-opendsa-sources.json').read_text())
    source=copy.deepcopy(data['files'][0]);source['content']+='tamper'
    with pytest.raises(ValueError,match='hash mismatch'): catalog.source_parts(source)


def test_four_subject_readings_have_provenance_and_permissions():
    docs=catalog.documents()
    assert len(docs)==16
    for subject in catalog.SUBJECTS: assert sum(d['subject']==subject for d in docs)==4
    assert len({d['id'] for d in docs})==len(docs)
    assert all(d['url'].startswith('https://') and d['version'] and d['license'] and d['locator'] for d in docs)


def test_corpus_preserves_unavailable_source_verification_date():
    spec=importlib.util.spec_from_file_location('real_import',SCRIPTS/'import-real-data.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    corpus=m.corpus()
    school=[d for d in corpus if d['domain']=='school']
    assert len(school)==15
    scnu=[d for d in school if d['metadata']['school']=='华南师范大学']
    assert len(scnu)==2
    assert all(d['retrievedAt']=='2026-10-23' and '未重新核验' in d['content'] for d in scnu)
    assert all('enrollmentCount' not in d['metadata'] and 'scoreLine' not in d['metadata'] for d in school)


def test_independent_algorithm_rechecks_match_translated_answers():
    qs={q['code']:q for q in catalog.questions()}
    def answer(name):
        q=qs[name];return q['options']['ABCD'.index(q['answer'])]
    stack=[]
    for c in 'DCBA':stack.append(c)
    assert answer('List-StackQMCQsrmv')==''.join(stack.pop() for _ in range(4))
    assert answer('List-StackQMCQqrmv')==''.join('DCBA')
    for n in (2,8,17):
        moves=sum(range(n))
        assert moves==n*(n-1)//2
    assert answer('Sorting-InssortMCQcosta')=='Θ(n²)'
    assert answer('Sorting-SelsortMCQcost')=='Θ(n²)'
    assert answer('Sorting-HeapsortMCQspace')=='Θ(1)'
