"""Independent, versioned replica corpus. Never connects to the business database."""
import hashlib
import json
import os
import re
from threading import Lock
from pathlib import Path
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5
from pydantic import Field, model_validator
from schemas import Reference, StrictModel
from source_policy import ReferenceSourcePolicy


class Document(StrictModel):
    id: str
    domain: str
    title: str
    url: str
    locator: str
    version: str
    retrievedAt: str
    license: str
    content: str = Field(min_length=1, max_length=50000)
    subject: str | None = None
    metadata: dict = Field(default_factory=dict)
    reviewStatus: str
    keywords: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def trusted_metadata(self):
        if self.domain not in {"knowledge", "school"} or self.reviewStatus != "verified":
            raise ValueError("仅接受已核验的 knowledge/school 资料")
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("来源必须为无凭证HTTPS链接")
        if not all((self.id, self.title, self.locator, self.version, self.retrievedAt, self.license)):
            raise ValueError("来源元数据不完整")
        return self

    def reference(self):
        return Reference(**self.model_dump(include=set(Reference.model_fields) - {"excerpt"}),
                         excerpt=self.content[:400])


def terms(text):
    text = text.lower()
    words = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    return set(words + [chinese[i:i+2] for i in range(len(chinese)-1)])


class Corpus:
    def __init__(self, path, policy_path=None):
        policy = ReferenceSourcePolicy(policy_path)
        raw = Path(path).read_bytes()
        records = json.loads(raw)
        self.records = records
        canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.checksum = hashlib.sha256(canonical).hexdigest()
        self.release_id = "rag-v1-" + self.checksum[:16]
        self.documents = [Document.model_validate(d) for d in records]
        for document in self.documents:
            policy.validate_url(document.url)
        if not self.documents or len({d.id for d in self.documents}) != len(self.documents):
            raise ValueError("资料为空或编号重复")
        self.by_id = {d.id: d for d in self.documents}
        self.chunks = []
        for d in self.documents:
            for start in range(0, len(d.content), 350):
                self.chunks.append(d.model_copy(update={"id": f"{d.id}#{start // 350}",
                    "content": d.content[start:start+450], "locator": f"{d.locator}；字符{start+1}起"}))
        self.chunk_by_id = {d.id: d for d in self.chunks}

    def lexical(self, query, domain, limit=5, subject=None):
        ranked, query_terms = [], terms(query)
        for d in self.chunks:
            if d.domain != domain or (subject and d.subject != subject):
                continue
            score = sum(len(t) for t in query_terms & terms(d.title + d.content) if len(t) > 1)
            score += 8 * sum(word.lower() in query.lower() for word in d.keywords)
            if score:
                ranked.append((score, d))
        return [d for _, d in sorted(ranked, key=lambda r: (-r[0], r[1].id))[:limit]]


class FastEmbedEncoder:
    def __init__(self, model):
        from fastembed import TextEmbedding
        self.model = TextEmbedding(model_name=model)

    def encode(self, texts):
        return [v.tolist() for v in self.model.embed(texts)]


class VectorIndex:
    def __init__(self, settings, corpus, encoder=None, client=None):
        from qdrant_client import QdrantClient
        self.settings, self.corpus, self.encoder = settings, corpus, encoder
        settings.RAG_INDEX.mkdir(parents=True, exist_ok=True)
        self.client = client or (QdrantClient(url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None, timeout=10) if settings.QDRANT_URL
            else QdrantClient(path=str(settings.RAG_INDEX / "qdrant"), force_disable_check_same_thread=True))
        fingerprint = hashlib.sha256((corpus.checksum + settings.EMBEDDING_MODEL).encode()).hexdigest()[:24]
        self.collection = "kaoyan_" + fingerprint
        self.marker = settings.RAG_INDEX / (self.collection + ".ready.json")

    def encode(self, texts):
        if self.encoder is None:
            self.encoder = FastEmbedEncoder(self.settings.EMBEDDING_MODEL)
        return self.encoder.encode(texts)

    def build(self):
        from qdrant_client import models as m
        archive = self.marker.with_suffix(".corpus.json")
        if not archive.exists():
            with archive.open("x", encoding="utf-8") as out:
                json.dump(self.corpus.records, out, ensure_ascii=False, indent=2)
        if self.marker.exists():
            if not self.client.collection_exists(self.collection):
                raise RuntimeError("集合缺失，请使用新索引目录重建")
            return
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
        vectors = self.encode([d.content for d in self.corpus.chunks])
        self.client.create_collection(self.collection,
            vectors_config=m.VectorParams(size=len(vectors[0]), distance=m.Distance.COSINE))
        self.client.upsert(self.collection, wait=True, points=[m.PointStruct(
            id=str(uuid5(NAMESPACE_URL, d.id)), vector=v, payload={"chunkId": d.id,
                "domain": d.domain, "subject": d.subject, "releaseId": self.corpus.release_id})
            for d, v in zip(self.corpus.chunks, vectors)])
        temp = self.marker.with_suffix(".tmp")
        temp.write_text(json.dumps({"checksum": self.corpus.checksum,
            "model": self.settings.EMBEDDING_MODEL, "chunks": len(vectors)}), encoding="utf-8")
        os.replace(temp, self.marker)

    def search(self, query, domain, limit=5, subject=None):
        from qdrant_client import models as m
        if not self.marker.exists():
            raise RuntimeError("向量索引尚未构建，请先执行 ingest.py")
        conditions = [m.FieldCondition(key="domain", match=m.MatchValue(value=domain)),
                      m.FieldCondition(key="releaseId", match=m.MatchValue(value=self.corpus.release_id))]
        if subject:
            conditions.append(m.FieldCondition(key="subject", match=m.MatchValue(value=subject)))
        hits = self.client.query_points(self.collection, query=self.encode([query])[0],
            query_filter=m.Filter(must=conditions), limit=limit,
            score_threshold=self.settings.RAG_MIN_SCORE).points
        return [self.corpus.chunk_by_id[h.payload["chunkId"]] for h in hits]

    def close(self):
        self.client.close()


class Retriever:
    def __init__(self, settings, corpus):
        self.settings, self.corpus, self.vector = settings, corpus, None
        self.lock = Lock()

    def search(self, query, domain="knowledge", limit=5, subject=None):
        if self.settings.RAG_BACKEND == "lexical":
            return self.corpus.lexical(query, domain, limit, subject)
        with self.lock:
            if self.vector is None:
                self.vector = VectorIndex(self.settings, self.corpus)
            return self.vector.search(query, domain, limit, subject)

    def close(self):
        if self.vector:
            self.vector.close()
