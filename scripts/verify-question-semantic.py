"""Self-authored engineering cases with a real local model; no paid provider or business DB."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'kaoyan-agent'))
# Weight downloads only use the public source, with caches inside this project.
os.environ.setdefault('HF_HOME', str(ROOT / 'kaoyan-agent/.cache/huggingface'))
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
os.environ.setdefault('HF_HUB_DISABLE_IMPLICIT_TOKEN', '1')
from config import Settings
from question_search import QuestionIndex, SearchQuestion, SearchRequest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('报告已存在，请使用新路径')
    settings = Settings(_env_file=None, AGENT_INTERNAL_KEY='evaluation-only-internal-key')
    # Topics on purpose do not help with lexical lookup.
    samples = [
        (1, '二叉树', '二叉树的结点性质。'),
        (2, '', '在二叉排序树中搜索给定元素。'),
        (3, '', '发送端根据网络拥塞调整数据发送速率。'),
        (4, '', '每个结点至多有两个子结点的树形结构。'),
        (5, '', '一棵具有左右孩子的树，给定先序和中序序列，求后序遍历序列。'),
        (6, '普通树', '一般树的表示方法。'),
        (7, '多叉树', '多叉树'),
        (8, '三叉树', '三叉树'),
        (9, '队列', '先进先出结构如何删除队头元素？'),
        (10, '操作系统', '进程切换时保存寄存器。'),
    ]
    cases = [
        ('二叉树', [1, 2, 4, 5], [6, 7, 8, 9, 10]),
        ('查找二叉搜索树的元素', [2], [6, 7, 8, 9, 10]),
        ('发送方根据网络拥堵调整发送速率', [3], [1, 6, 7, 8, 9, 10]),
        ('每个节点最多有两个孩子的树', [4, 5], [6, 7, 8, 9, 10]),
    ]
    with tempfile.TemporaryDirectory(prefix='question-real-model-') as temp:
        settings.QUESTION_INDEX = Path(temp)
        index = QuestionIndex(settings)
        try:
            start = time.monotonic()
            response = index.submit([SearchQuestion(id=i, version=1, knowledgePoint=point, content=text) for i, point, text in samples])
            release = response['releaseId']
            deadline = start + 180
            while index.status(release)['status'] == 'BUILDING':
                if time.monotonic() > deadline:
                    raise TimeoutError('本地模型准备超时')
                time.sleep(.05)
            if index.status(release)['status'] != 'READY':
                raise RuntimeError('模型或索引未准备完成')
            cold = time.monotonic() - start
            results = []
            for query, positive, negative in cases:
                started = time.monotonic()
                result = index.search(SearchRequest(releaseId=release, query=query, allowedIds=[s[0] for s in samples]))
                ids = {m['id'] for m in result['matches']}
                results.append({'query': query, 'expectedRelevant': positive, 'expectedIrrelevant': negative,
                    'matches': result['matches'], 'missed': sorted(set(positive)-ids),
                    'falsePositives': sorted(set(negative)&ids), 'seconds': round(time.monotonic()-started, 4)})
        finally:
            index.close()
    report = {'scope': 'self-authored engineering cases; real local FastEmbed + embedded Qdrant; no human domain review',
        'model': settings.EMBEDDING_MODEL, 'threshold': settings.QUESTION_MIN_SCORE,
        'releaseId': release, 'coldBuildSeconds': round(cold, 4), 'paidModelCalls': 0, 'cases': results,
        'modelSource': 'https://huggingface.co/BAAI/bge-small-zh-v1.5', 'modelLicense': 'MIT',
        'limits': 'Short topics can miss unlabeled questions; scores are not probabilities. Cases are not a representative benchmark.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'report': str(args.output), 'coldBuildSeconds': report['coldBuildSeconds'],
        'cases': len(results), 'missed': sum(len(r['missed']) for r in results),
        'falsePositives': sum(len(r['falsePositives']) for r in results)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
