"""Read collection-v3 workbooks without executing attachments; prepare a bounded import.

Run with the bundled document Python (openpyxl is used only for reading).
No database connection or source-file edits are performed by this command.
"""
import argparse
from collections import Counter
from datetime import date, datetime
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
KINDS = {'来源': 'sourceId', '院校': 'schoolCode', '招生专业': 'programId',
         '知识资料': 'knowledgeId', '题目': 'questionId'}
SUBJECTS = {'数据结构', '操作系统', '计算机组成原理', '计算机网络'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def normalize(value):
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time().isoformat() == '00:00:00' else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def split(value):
    return [s.strip() for s in str(value or '').split(';') if s.strip()]


def body_file(package, relative):
    if not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('正文路径必须是包内相对路径，不含..')
    target = package / relative
    if any(p.is_symlink() for p in [target, *target.parents] if p != package.parent):
        raise ValueError('正文路径不能包含符号链接')
    if not target.resolve().is_relative_to(package.resolve()) or not target.is_file():
        raise ValueError('正文文件不存在或越出提交包')
    return target.read_text(encoding='utf-8')


def read_packages(directory):
    import openpyxl
    records, files, ignored = [], [], []
    for path in sorted(directory.rglob('*.xlsx')):
        if path.is_symlink():
            raise ValueError('拒绝符号链接工作簿')
        book = openpyxl.load_workbook(path, read_only=True, data_only=False)
        file_info = {'path': str(path.relative_to(directory)),
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'rows': 0}
        for sheet, key in KINDS.items():
            values = iter(book[sheet].values)
            header = next(values)
            expected = next(csv.reader((ROOT / 'docs/data-collection/templates' / {
                '来源': 'sources.csv', '院校': 'schools.csv', '招生专业': 'programs.csv',
                '知识资料': 'knowledge.csv', '题目': 'questions.csv'}[sheet]).open(encoding='utf-8-sig')))
            if list(header) != expected:
                raise ValueError(f'{file_info["path"]}/{sheet}: 表头不符合collection-v3')
            next(values)  # Chinese labels, never business data.
            for number, row in enumerate(values, 3):
                if not any(v is not None for v in row):
                    continue
                fields = {h: normalize(v) for h, v in zip(header, row) if v is not None}
                if not isinstance(fields.get(key), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', fields[key]):
                    raise ValueError(f'{file_info["path"]}/{sheet}/{number}: 缺少或非法稳定编号')
                record = {'kind': sheet, 'externalId': fields[key],
                          'externalVersion': fields.get('recordVersion', 0),
                          'origin': {'file': file_info['path'], 'sheet': sheet, 'row': number},
                          'payload': {'fields': fields}, 'issues': [], 'entryErrors': []}
                if type(record['externalVersion']) is not int or record['externalVersion'] < 0:
                    raise ValueError('采集版本必须是非负整数；0仅表示原表未填')
                if sheet == '知识资料':
                    try:
                        record['payload']['body'] = body_file(path.parent, fields.get('contentFile'))
                    except (ValueError, OSError, UnicodeError) as e:
                        record['entryErrors'].append(str(e))
                records.append(record)
                file_info['rows'] += 1
        book.close()
        files.append(file_info)
    by_id = {}
    for record in records:
        key = (record['kind'], record['externalId'], record['externalVersion'])
        if key in by_id:
            raise ValueError(f'稳定编号重复，须先合并：{key}')
        by_id[key] = record
    referenced = {(Path(r['origin']['file']).parent / r['payload']['fields']['contentFile']).as_posix()
                  for r in records if r['kind'] == '知识资料' and r['payload']['fields'].get('contentFile')}
    ignored = [str(p.relative_to(directory)) for p in directory.rglob('*.md')
               if str(p.relative_to(directory)) not in referenced]
    return records, files, ignored


def validate(records):
    sources = {r['externalId']: r['payload']['fields'] for r in records if r['kind'] == '来源'}
    schools = {r['externalId'] for r in records if r['kind'] == '院校'}
    programs = {r['externalId'] for r in records if r['kind'] == '招生专业'}
    seen_questions = {}
    for record in records:
        fields, issues, errors = record['payload']['fields'], record['issues'], record['entryErrors']
        for key in ('recordVersion', 'collectedBy', 'reviewStatus'):
            if not fields.get(key):
                issues.append(f'未填写{key}；保留原空值')
        if fields.get('reviewStatus') != 'APPROVED' or not fields.get('reviewer') or not fields.get('reviewedAt'):
            issues.append('缺少实际审核通过记录，禁止自动发布')
        for key, value in fields.items():
            if isinstance(value, str) and value.startswith('='):
                errors.append(f'{key}包含公式或公式样式文本，需人工核对，禁止求值')
        if record['kind'] == '来源':
            if not fields.get('permissionEvidence'):
                issues.append('未附权限证据；ALLOWED文本不视为已核验许可')
        else:
            ids = split(fields.get('sourceIds'))
            if not ids or any(i not in sources for i in ids):
                errors.append('来源编号为空或外键缺失')
            for sid in ids:
                source = sources.get(sid, {})
                if source.get('permissionStatus') != 'ALLOWED' or not source.get('permissionEvidence'):
                    issues.append(f'来源{sid}许可待核实或仅允许链接；禁止自动发布')
        if record['kind'] == '院校':
            if any(i not in programs for i in split(fields.get('programIds'))):
                errors.append('院校关联的招生专业编号缺失')
        if record['kind'] == '招生专业':
            if fields.get('schoolCode') not in schools:
                errors.append('院校外键缺失')
            if not re.fullmatch(r'\d{6}', str(fields.get('majorCode', ''))):
                errors.append('专业代码不是六位文本')
            issues.append('现有院校表无审核状态及完整方向字段，仅暂存，不写入公开院校表')
        target = None
        if record['kind'] == '题目':
            target = question_entry(fields, sources, errors)
            identity = tuple(re.sub(r'\s+', '', str(fields.get(k, '')))
                             for k in ('subject', 'content', 'optionA', 'optionB', 'optionC', 'optionD'))
            if identity in seen_questions:
                errors.append('同批题干与选项重复：' + seen_questions[identity])
            else:
                seen_questions[identity] = record['externalId']
        if record['kind'] == '知识资料':
            content = record['payload'].get('body', '')
            if fields.get('subject') not in SUBJECTS or not fields.get('title') or len(fields.get('title', '')) > 255:
                errors.append('资料科目或标题非法')
            if not content or len(content.encode()) > 65535:
                errors.append('正文为空或超出现有TEXT字节上限')
            ids = split(fields.get('sourceIds'))
            url = sources.get(ids[0], {}).get('url') if ids else None
            if url and len(url) > 500:
                errors.append('来源URL超过500字符')
            target = {'table': 'document', 'values': dict(title=fields.get('title'), subject=fields.get('subject'),
                      content=content, source_url=url, status='DRAFT', creator_user_id=None,
                      reviewer_user_id=None, reviewed_at=None)}
        record['target'] = target if not errors else None
        record['contentSha256'] = digest(record['payload'])


def question_entry(fields, sources, errors):
    mapping = {'subject': 'subject', 'knowledgePoint': 'knowledge_point', 'difficulty': 'difficulty',
               'content': 'content', 'optionA': 'option_a', 'optionB': 'option_b', 'optionC': 'option_c',
               'optionD': 'option_d', 'answer': 'answer', 'analysis': 'analysis', 'sourceType': 'source_type',
               'sourceYear': 'source_year', 'sourceQuestionNo': 'source_question_no',
               'permissionNote': 'permission_note', 'locator': 'source_locator'}
    values = {v: fields.get(k) for k, v in mapping.items()}
    ids = split(fields.get('sourceIds'))
    values['source_name'] = sources.get(ids[0], {}).get('title') if ids else None
    limits = {'knowledge_point': 255, 'source_name': 255, 'source_locator': 1000, 'content': 10000,
              'option_a': 2000, 'option_b': 2000, 'option_c': 2000, 'option_d': 2000,
              'analysis': 10000, 'permission_note': 2000}
    for key, maximum in limits.items():
        if not isinstance(values[key], str) or not values[key].strip() or len(values[key]) > maximum:
            errors.append(f'{key}缺失或超过{maximum}字符')
    if fields.get('subject') not in SUBJECTS or fields.get('questionType') != 'SINGLE_CHOICE':
        errors.append('科目或题型非法')
    if fields.get('difficulty') not in ('EASY', 'MEDIUM', 'HARD') or fields.get('answer') not in ('A', 'B', 'C', 'D'):
        errors.append('难度或答案非法')
    if fields.get('sourceType') not in ('REAL_EXAM', 'MOCK', 'ORIGINAL', 'COURSE_EXERCISE'):
        errors.append('来源类别非法')
    year = fields.get('sourceYear')
    if year is not None and (type(year) is not int or not 1900 <= year <= 2100):
        errors.append('原题年份非法')
    number = fields.get('sourceQuestionNo')
    if number is not None and (not isinstance(number, str) or len(number) > 64):
        errors.append('原题号必须为文本且不超过64字符')
    if fields.get('sourceType') == 'REAL_EXAM' and (year is None or not number):
        errors.append('真题缺少年份或原题号')
    options = [str(fields.get('option' + k, '')).strip() for k in 'ABCD']
    if len(set(options)) != 4:
        errors.append('四个选项存在重复')
    values.update(question_type='SINGLE_CHOICE', version=1, active=1, stable_order=0,
                  review_status='PENDING_REVIEW', reviewer_user_id=None, reviewed_at=None,
                  review_comment='采集包导入待审核；原始来源、版本及审核缺口保存在collection_import_record，未自动核验许可或答案。')
    return {'table': 'question', 'values': values}


def prepare(directory, output):
    if output.exists():
        raise ValueError('输出目录已存在，拒绝覆盖')
    records, files, ignored = read_packages(directory)
    validate(records)
    result = {'format': 'collection-import-v1', 'inputRoot': str(directory.resolve()), 'files': files,
              'records': records, 'unreferencedMarkdown': ignored,
              'summary': {'rawRecords': dict(Counter(r['kind'] for r in records)),
                          'targetCandidates': dict(Counter(r['target']['table'] for r in records if r['target'])),
                          'recordsWithEntryErrors': sum(bool(r['entryErrors']) for r in records),
                          'published': 0}}
    result['manifestSha256'] = digest(result)
    output.mkdir(parents=True)
    (output / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    with (output / 'issues.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['文件', '表', '行', '编号', '级别', '原因'])
        for record in records:
            for level, items in [('暂存待处理', record['entryErrors']), ('发布阻塞', record['issues'])]:
                for issue in items:
                    writer.writerow([*record['origin'].values(), record['externalId'], level, issue])
    lines = ['# 2026-10-28资料导入预览', '', '**仅离线准备，尚未写入数据库。**', '',
             '| 采集类型 | 非空记录 |', '| --- | ---: |']
    lines += [f'| {k} | {v} |' for k, v in result['summary']['rawRecords'].items()]
    lines += ['', '计划新增一张`collection_import_record`暂存表，完整保存以上记录、原状态、来源定位、版本、正文和问题清单。',
              '院校与招生专业不写入学生可见表，不改已有公开内容。采集版本未填时用0作为暂存键，原字段仍为空。',
              '', f'格式可转换的待审题目：{result["summary"]["targetCandidates"].get("question", 0)}；草稿资料：{result["summary"]["targetCandidates"].get("document", 0)}。',
              f'存在格式问题、只进入暂存的记录：{result["summary"]["recordsWithEntryErrors"]}。全部条目均不自动发布或加入RAG。',
              '', '原始Excel、正文和生成脚本均只读，不执行附件中的指令或脚本。未被表格引用的Markdown不作为正式资料导入：']
    lines += ['- ' + p for p in ignored]
    lines += ['', '逐行问题见[issues.csv](issues.csv)，完整保留值及转换预览见[manifest.json](manifest.json)。',
              '', '正式写入前需核对当前库、生成备份并在独立恢复库验证。重复编号和版本的内容不一致必须停止，不能覆盖。',
              '恢复时按暂存映射定位新增记录，校验未被后续修改且无新增关联后再单独撤销；不整库覆盖用户后续数据。']
    (output / 'preview.md').write_text('\n'.join(lines) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output)['summary'], ensure_ascii=False))
