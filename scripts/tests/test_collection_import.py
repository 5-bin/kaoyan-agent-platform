"""Offline regression checks for the collection ingestion boundary."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


prepare = module('prepare_collection_test', 'prepare-collection-import.py')
importer = module('apply_collection_test', 'import-collected-data.py')


def test_body_rejects_traversal_and_symlinks(tmp_path):
    package = tmp_path / 'package'
    package.mkdir()
    outside = tmp_path / 'outside.md'
    outside.write_text('not package data')
    (package / 'linked.md').symlink_to(outside)
    for path in ('../outside.md', str(outside), 'linked.md', 'missing.md'):
        with pytest.raises(ValueError):
            prepare.body_file(package, path)
    (package / 'body.md').write_text('正文')
    assert prepare.body_file(package, 'body.md') == '正文'


def question():
    return dict(subject='数据结构', knowledgePoint='树', difficulty='EASY', questionType='SINGLE_CHOICE',
                content='问题', optionA='甲', optionB='乙', optionC='丙', optionD='丁', answer='A',
                analysis='推理', sourceType='REAL_EXAM', sourceIds='SRC-A', locator='原题', permissionNote='待核实')


def test_true_exam_requires_year_and_number_and_never_publishes():
    fields = question()
    errors = []
    result = prepare.question_entry(fields, {'SRC-A': {'title': '来源'}}, errors)
    assert '真题缺少年份或原题号' in errors
    assert result['values']['review_status'] == 'PENDING_REVIEW'
    assert result['values']['reviewer_user_id'] is None
    assert result['values']['reviewed_at'] is None
    fields.update(sourceYear=2024, sourceQuestionNo='1')
    errors = []
    prepare.question_entry(fields, {'SRC-A': {'title': '来源'}}, errors)
    assert not errors


def test_incomplete_or_duplicate_options_are_not_silently_repaired():
    fields = question()
    fields.update(answer=None, optionD='甲')
    errors = []
    prepare.question_entry(fields, {'SRC-A': {'title': '来源'}}, errors)
    assert '四个选项存在重复' in errors
    assert '难度或答案非法' in errors
    assert fields['answer'] is None


def test_manifest_rejects_tampering_and_publishing(tmp_path):
    fields = question()
    payload = {'fields': fields}
    target_row = {'kind': '题目', 'payload': payload, 'contentSha256': importer.digest(payload),
                  'target': prepare.question_entry(fields, {'SRC-A': {'title': '来源'}}, [])}
    manifest = {'format': 'collection-import-v1', 'records': [target_row]}
    manifest['manifestSha256'] = importer.digest(manifest)
    target_row['target']['values']['review_status'] = 'APPROVED'
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match='校验和'):
        importer.load_manifest(path)
    manifest.pop('manifestSha256')
    manifest['manifestSha256'] = importer.digest(manifest)
    path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match='禁止导入发布状态'):
        importer.load_manifest(path)


def test_sql_literals_do_not_execute_attached_text():
    value = "'); DROP TABLE user; -- $(cat .env) `whoami`"
    literal = importer.sql(value)
    assert value not in literal
    assert literal == 'CONVERT(0x' + value.encode().hex() + ' USING utf8mb4)'


def test_same_external_version_conflict_aborts_before_insert():
    row = {'kind': '来源', 'externalId': 'SRC-A', 'externalVersion': 1,
           'contentSha256': importer.digest({'fields': {'title': 'new'}})}
    class Database:
        name = 'fake'
        def tables(self):
            return [importer.STAGING]
        def records(self, table):
            assert table == importer.STAGING
            payload = {'fields': {'title': 'old'}}
            return [dict(record_type='来源', external_id='SRC-A', external_version=1,
                         payload=payload, content_sha256=importer.digest(payload))]
    with pytest.raises(RuntimeError, match='同编号、同版本'):
        importer.inspect(Database(), {'records': [row]})
