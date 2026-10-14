"""Run before the Agent; imports are local and never call a paid LLM."""
from config import Settings
from retrieval import Corpus, VectorIndex

if __name__ == "__main__":
    settings = Settings()
    corpus = Corpus(settings.RAG_DATA)
    index = VectorIndex(settings, corpus)
    try:
        index.build()
        print(f"索引就绪：{corpus.release_id}，{len(corpus.chunks)} 个资料块，{settings.EMBEDDING_MODEL}")
    finally:
        index.close()
