"""Independent, versioned replica corpus. Never connects to the business database."""
import hashlib
import json
import logging
import math
import os
import re
from collections import Counter
from threading import Lock
from pathlib import Path
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5
from pydantic import Field, model_validator
from core.errors import ToolUnavailable
from schemas import Reference, StrictModel
from source_policy import ReferenceSourcePolicy

log = logging.getLogger(__name__)


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


def bm25_tokens(text):
    """Chinese unigrams + bigrams and ASCII words. No external tokenizer needed."""
    text = text.lower()
    words = re.findall(r"[a-z0-9]+", text)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    return words + list(chinese) + [chinese[i:i+2] for i in range(len(chinese)-1)]


class BM25Index:
    """Small in-memory BM25 baseline over the immutable corpus chunks."""

    def __init__(self, chunks, k1=1.5, b=0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        tokenized = [bm25_tokens(d.title + " " + d.content + " " + " ".join(d.keywords)) for d in chunks]
        self.lengths = [len(values) for values in tokenized]
        self.avgdl = sum(self.lengths) / max(1, len(self.lengths))
        self.term_freq = [Counter(values) for values in tokenized]
        self.doc_freq = Counter()
        for values in tokenized:
            self.doc_freq.update(values)
        self.total = len(chunks)

    def search(self, query, domain, limit=5, subject=None):
        if not self.total:
            return []
        candidates = set(bm25_tokens(query))
        # Multi-character queries must match a bigram or ASCII word. Single
        # Chinese characters are too common ("次" in "层次") to be useful.
        wanted = {term for term in candidates if len(term) > 1} or candidates
        ranked = []
        for index, chunk in enumerate(self.chunks):
            if chunk.domain != domain or (subject and chunk.subject != subject):
                continue
            score = 0.0
            for term in wanted:
                frequency = self.term_freq[index].get(term, 0)
                if not frequency:
                    continue
                document_frequency = self.doc_freq.get(term, 0)
                idf = math.log(1 + (self.total - document_frequency + 0.5) / (document_frequency + 0.5))
                normalizer = frequency + self.k1 * (
                    1 - self.b + self.b * self.lengths[index] / max(self.avgdl, 1e-9))
                score += idf * frequency * (self.k1 + 1) / normalizer
            if score > 0:
                ranked.append((score, chunk))
        ranked.sort(key=lambda row: (-row[0], row[1].id))
        return [chunk for _, chunk in ranked[:limit]]


SUBJECT_NAMES = {
    "数据结构": ("数据结构",),
    "计算机组成原理": ("计算机组成原理", "组成原理"),
    "操作系统": ("操作系统",),
    "计算机网络": ("计算机网络",),
}
SUBJECT_HINTS = (
    ("数据结构", ("栈", "队列", "链表", "二叉树", "图", "排序", "查找", "散列", "哈希")),
    ("计算机组成原理", ("主存", "存储层次", "指令", "总线", "浮点", "cache", "缓存")),
    ("操作系统", ("进程", "线程", "死锁", "调度", "虚拟内存", "文件系统", "信号量")),
    ("计算机网络", ("协议栈", "tcp/ip", "tcp", "udp", "ip", "路由", "拥塞", "http", "dns", "以太网")),
)


def _term_pattern(term):
    """ASCII terms match whole words ("ip" not in "pipeline"); Chinese terms match as written."""
    escaped = re.escape(term.lower())
    return rf"(?<![a-z0-9]){escaped}(?![a-z0-9])" if re.fullmatch(r"[a-z0-9/]+", term.lower()) else escaped


def mentions(text, term):
    """Whether text contains a subject term; "tcp/ip" is mentioned by either part."""
    parts = term.split("/") if "/" in term else [term]
    return any(re.search(_term_pattern(part), (text or "").lower()) for part in parts if part)


def subject_terms(text):
    """Return (subject, anchor terms) from non-overlapping hints, longest first.

    An explicit subject name wins. Otherwise longer hints consume the shorter
    ones they contain, so "协议栈" is network and its "栈" no longer counts for
    data structures; hints still spanning several subjects ("主存和虚拟内存")
    return no subject and the caller searches unfiltered. Anchors are the topical
    terms a relevant chunk must mention; subject names are not anchors.
    """
    lowered = (text or "").lower()
    spans = []
    for subject, hints in [*SUBJECT_NAMES.items(), *SUBJECT_HINTS]:
        for hint in hints:
            for match in re.finditer(_term_pattern(hint), lowered):
                spans.append((match.start(), match.end(), subject, hint.lower()))
    spans.sort(key=lambda span: (span[0] - span[1], span[0]))
    taken, kept = set(), []
    for start, end, subject, hint in spans:
        if taken.isdisjoint(range(start, end)):
            taken.update(range(start, end))
            kept.append((subject, hint, end - start))
    names = {name for name, values in SUBJECT_NAMES.items() for value in values}
    anchors = tuple(dict.fromkeys(hint for _, hint, _ in kept if hint not in names))
    named = {subject for subject, hint, _ in kept if hint in names}
    subjects = named or {subject for subject, _, _ in kept}
    return (next(iter(subjects)) if len(subjects) == 1 else None), anchors


def detect_subject(text):
    """Best-effort subject hint. Callers must fall back to unfiltered search."""
    return subject_terms(text)[0]


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
        self._bm25, self._bm25_lock = None, Lock()

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

    def bm25(self, query, domain, limit=5, subject=None):
        if self._bm25 is None:
            with self._bm25_lock:
                if self._bm25 is None:
                    self._bm25 = BM25Index(self.chunks)
        return self._bm25.search(query, domain, limit, subject)


class FastEmbedEncoder:
    def __init__(self, model, cache_dir=None, threads=None, local_files_only=False):
        from fastembed import TextEmbedding
        try:
            self.model = TextEmbedding(model_name=model, cache_dir=cache_dir, threads=threads, local_files_only=local_files_only)
        except ValueError as error:
            if not local_files_only:
                raise
            # fastembed reports a missing local cache as ValueError; it is an
            # expected availability failure that hybrid search can fall back from.
            raise ToolUnavailable("嵌入模型权重缓存缺失，请先运行 ingest.py 准备") from error

    def encode(self, texts):
        return [v.tolist() for v in self.model.embed(texts)]


class VectorIndex:
    def __init__(self, settings, corpus, encoder=None, client=None, local_files_only=False):
        from qdrant_client import QdrantClient
        self.settings, self.corpus, self.encoder = settings, corpus, encoder
        self.local_files_only = local_files_only
        fingerprint = hashlib.sha256((corpus.checksum + settings.EMBEDDING_MODEL).encode()).hexdigest()[:24]
        self.collection = "kaoyan_" + fingerprint
        self.marker = settings.RAG_INDEX / (self.collection + ".ready.json")
        if local_files_only and not self.marker.is_file():
            raise ToolUnavailable("向量索引尚未构建，请先执行 ingest.py")
        if local_files_only and not settings.QDRANT_URL and not (settings.RAG_INDEX / "qdrant").is_dir():
            raise ToolUnavailable("向量索引存储缺失，请检查现有索引")
        settings.RAG_INDEX.mkdir(parents=True, exist_ok=True)
        self.client = client or (QdrantClient(url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None, timeout=10) if settings.QDRANT_URL
            else QdrantClient(path=str(settings.RAG_INDEX / "qdrant"), force_disable_check_same_thread=True))

    def encode(self, texts):
        if self.encoder is None:
            # Share the project embedding cache with question search; the library
            # default lives in the OS temp dir and can be wiped, forcing a
            # download inside a request.
            self.encoder = FastEmbedEncoder(self.settings.EMBEDDING_MODEL,
                cache_dir=str(self.settings.QUESTION_MODEL_CACHE),
                local_files_only=self.local_files_only)
        return self.encoder.encode(texts)

    def build(self):
        from qdrant_client import models as m
        archive = self.marker.with_suffix(".corpus.json")
        if not archive.exists():
            with archive.open("x", encoding="utf-8") as out:
                json.dump(self.corpus.records, out, ensure_ascii=False, indent=2)
        if self.marker.exists():
            if not self.client.collection_exists(self.collection):
                raise ToolUnavailable("集合缺失，请使用新索引目录重建")
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
            raise ToolUnavailable("向量索引尚未构建，请先执行 ingest.py")
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
    def __init__(self, settings, corpus, local_files_only=False):
        self.settings, self.corpus, self.vector = settings, corpus, None
        self.local_files_only = local_files_only
        self.lock = Lock()

    def _vector_index(self):
        with self.lock:
            if self.vector is None:
                self.vector = VectorIndex(self.settings, self.corpus,
                    local_files_only=self.local_files_only)
            return self.vector

    def search(self, query, domain="knowledge", limit=5, subject=None):
        backend = self.settings.RAG_BACKEND
        if backend == "lexical":
            return _dedupe(self.corpus.lexical(query, domain, limit, subject))
        if backend == "bm25":
            return _dedupe(self.corpus.bm25(query, domain, limit, subject))
        if backend == "qdrant":
            return _dedupe(self._vector_index().search(query, domain, limit, subject))
        if backend == "hybrid":
            # Reciprocal-rank fusion; lexical remains available when the vector
            # index is absent so a demo does not fail before `ingest.py` ran.
            lexical = self.corpus.bm25(query, domain, 20, subject)
            vector = []
            try:
                vector = self._vector_index().search(query, domain, 20, subject)
            except (RuntimeError, ImportError, OSError, *_vector_failures()) as error:
                # Remote Qdrant/connection errors are not RuntimeError subclasses.
                log.warning("hybridVectorFailure=%s", type(error).__name__)
            fused = {}
            for rank, doc in enumerate(lexical):
                fused[doc.id] = fused.get(doc.id, 0.0) + 1 / (60 + rank + 1)
            for rank, doc in enumerate(vector):
                fused[doc.id] = fused.get(doc.id, 0.0) + 1 / (60 + rank + 1)
            ranked = sorted(fused.items(), key=lambda row: (-row[1], row[0]))
            return _dedupe([self.corpus.chunk_by_id[key] for key, _ in ranked])[:limit]
        raise ValueError("未知检索后端")

    def close(self):
        if self.vector:
            self.vector.close()


def _vector_failures():
    """Expected Qdrant client failures; empty when the optional client is absent."""
    try:
        from qdrant_client.http.exceptions import ApiException
    except ImportError:
        return ()
    return (ApiException,)


def _dedupe(chunks):
    """Keep the first chunk of each document; citations stay document-level."""
    seen, result = set(), []
    for chunk in chunks:
        base = chunk.id.split("#", 1)[0]
        if base in seen:
            continue
        seen.add(base)
        result.append(chunk)
    return result
