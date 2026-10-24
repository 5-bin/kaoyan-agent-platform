"""Explicit offline cleanup of old question collections. Preview unless --apply."""
import argparse
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'kaoyan-agent'))
from config import Settings
from qdrant_client import QdrantClient


def main():
    parser = argparse.ArgumentParser(description='Stop the Agent through your normal authorized process before opening its local store.')
    parser.add_argument('--keep', required=True, action='append', help='Complete questions-<32 hex> release to retain; repeat for multiple releases')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if any(not re.fullmatch(r'questions-[a-f0-9]{32}', value) for value in args.keep):
        parser.error('索引版本格式不正确')
    root = Settings().QUESTION_INDEX
    if not (root / 'qdrant').is_dir():
        parser.error('题目索引不存在')
    client = QdrantClient(path=str(root / 'qdrant'))
    try:
        keep = {name.replace('-', '_') for name in args.keep}
        existing = {collection.name for collection in client.get_collections().collections}
        if not keep <= existing:
            parser.error('需要保留的索引不存在，拒绝清理')
        obsolete = sorted(name for name in existing if re.fullmatch(r'questions_[a-f0-9]{32}', name) and name not in keep)
        for collection in obsolete:
            print(('清理：' if args.apply else '预览：') + collection.replace('_', '-'))
            if args.apply:
                client.delete_collection(collection)
                (root / (collection.replace('_', '-') + '.ready.json')).unlink(missing_ok=True)
        print(f'共{len(obsolete)}个旧索引；' + ('清理完成。' if args.apply else '未执行删除。'))
    finally:
        client.close()


if __name__ == '__main__':
    main()
