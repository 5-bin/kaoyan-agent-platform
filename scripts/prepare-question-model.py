"""Prepare the configured public embedding model once; no business data is read."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
os.environ['HF_HUB_DISABLE_XET'] = '1'
os.environ.setdefault('HF_HOME', str(ROOT / 'kaoyan-agent/.cache/huggingface'))
sys.path.insert(0, str(ROOT / 'kaoyan-agent'))
from config import Settings
from retrieval import FastEmbedEncoder

if __name__ == '__main__':
    settings = Settings()
    encoder = FastEmbedEncoder(settings.EMBEDDING_MODEL, cache_dir=str(settings.QUESTION_MODEL_CACHE), threads=2)
    vector = encoder.encode(['本地模型准备检查'])[0]
    print(f'本地题目模型就绪：{settings.EMBEDDING_MODEL}，维度{len(vector)}。未调用付费模型或读取业务数据库。')
