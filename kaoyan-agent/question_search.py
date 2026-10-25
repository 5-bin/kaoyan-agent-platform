"""Public question vectors only. Authorized historical overrides never leave memory."""
import hashlib
import json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import RLock
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, model_validator
from schemas import StrictModel
from retrieval import FastEmbedEncoder


class SearchQuestion(StrictModel):
    id: int = Field(gt=0)
    version: int | None = Field(default=None, ge=1)
    subject: str = Field(default="", max_length=50)
    difficulty: str = Field(default="", max_length=50)
    knowledgePoint: str = Field(default="", max_length=255)
    content: str = Field(min_length=1, max_length=50000)
    optionA: str = Field(default="", max_length=10000)
    optionB: str = Field(default="", max_length=10000)
    optionC: str = Field(default="", max_length=10000)
    optionD: str = Field(default="", max_length=10000)

    def text(self):
        return "\n".join([self.knowledgePoint, self.content, self.optionA, self.optionB, self.optionC, self.optionD])


class IndexRequest(StrictModel):
    questions: list[SearchQuestion] = Field(max_length=10000)

    @model_validator(mode="after")
    def unique_questions(self):
        if len({q.id for q in self.questions}) != len(self.questions):
            raise ValueError("duplicate question")
        return self


class SearchRequest(StrictModel):
    releaseId: str = Field(pattern=r"^questions-[a-f0-9]{32}$")
    query: str = Field(min_length=1, max_length=255)
    allowedIds: list[int] = Field(max_length=10000)
    overrides: list[SearchQuestion] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="after")
    def authorized_overrides(self):
        if (any(i <= 0 for i in self.allowedIds) or len(set(self.allowedIds)) != len(self.allowedIds)
                or len({q.id for q in self.overrides}) != len(self.overrides)
                or not {q.id for q in self.overrides} <= set(self.allowedIds)):
            raise ValueError("invalid candidates")
        return self


def topic_matches(query, label):
    def norm(text):
        return re.sub(r"\s+", "", text).upper().replace("传输控制协议", "TCP").replace("用户数据报协议", "UDP").replace("TCP协议", "TCP").replace("UDP协议", "UDP")
    query, label = norm(query), norm(label)
    left = r"(?<![A-Z0-9])" if query and query[0].isascii() and query[0].isalnum() else ""
    right = r"(?![A-Z0-9])" if query and query[-1].isascii() and query[-1].isalnum() else ""
    return bool(query and re.search(left + re.escape(query) + right, label))


def cosine(a, b):
    denominator = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return sum(x*y for x, y in zip(a, b)) / denominator if denominator else 0.0


def conflicts_with_topic(query, question):
    # A close vector for 三叉树 must not override an explicit 二叉树 constraint.
    requested = set(re.findall(r"([二三四五六七八九十\d多])叉", query))
    actual = set(re.findall(r"([二三四五六七八九十\d多])叉", question.knowledgePoint + question.content))
    return bool(requested and actual and not requested.intersection(actual))


class QuestionIndex:
    def __init__(self, settings, encoder=None):
        self.settings, self.encoder = settings, encoder
        self.root = Path(settings.QUESTION_INDEX)
        self.lock = RLock()
        self.encode_lock = RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="question-index")
        self.jobs = {}
        self.client = None

    def _client(self):
        if self.client is None:
            from qdrant_client import QdrantClient
            self.root.mkdir(parents=True, exist_ok=True)
            # Separate local store even if knowledge RAG uses remote Qdrant.
            self.client = QdrantClient(path=str(self.root / "qdrant"), force_disable_check_same_thread=True)
        return self.client

    def encode(self, texts):
        with self.encode_lock:
            if self.encoder is None:
                self.encoder = FastEmbedEncoder(self.settings.EMBEDDING_MODEL, cache_dir=str(self.settings.QUESTION_MODEL_CACHE), threads=2, local_files_only=True)
            vectors = self.encoder.encode(texts)
            if len(vectors) != len(texts) or any(not v or not all(math.isfinite(x) for x in v) for v in vectors):
                raise ValueError("invalid vectors")
            return vectors

    def submit(self, questions):
        records = [q.model_dump() for q in sorted(questions, key=lambda q: q.id)]
        data = json.dumps({"model": self.settings.EMBEDDING_MODEL, "questions": records}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        release = "questions-" + hashlib.sha256(data.encode()).hexdigest()[:32]
        with self.lock:
            state = self.status(release)
            if state["status"] in {"READY", "BUILDING"}:
                return state
            if sum(not job.done() for job in self.jobs.values()) >= 2:
                return {"releaseId": release, "status": "BUSY"}
            if len(self.jobs) >= 128:
                self.jobs = {key: job for key, job in self.jobs.items() if not job.done()}
            self.jobs[release] = self.executor.submit(self._build, release, records)
        return {"releaseId": release, "status": "BUILDING"}

    def status(self, release):
        with self.lock:
            if (self.root / (release + ".ready.json")).is_file():
                if self._client().collection_exists(release.replace("-", "_")):
                    return {"releaseId": release, "status": "READY"}
                return {"releaseId": release, "status": "FAILED"}
            job = self.jobs.get(release)
            return {"releaseId": release, "status": "NOT_FOUND" if job is None else
                    "BUILDING" if not job.done() else "FAILED"}

    def _build(self, release, records):
        try:
            from qdrant_client import models as m
            questions = [SearchQuestion(**r) for r in records]
            vectors = self.encode([q.text() for q in questions]) if questions else self.encode(["空题库"])
            collection = release.replace("-", "_")
            with self.lock:
                client = self._client()
                if not client.collection_exists(collection):
                    client.create_collection(collection, vectors_config=m.VectorParams(size=len(vectors[0]), distance=m.Distance.COSINE))
                for start in range(0, len(questions), 128):
                    client.upsert(collection, wait=True, points=[m.PointStruct(
                        id=str(uuid5(NAMESPACE_URL, f"{release}:{q.id}")), vector=v,
                        payload={"questionId": q.id, "version": q.version})
                        for q, v in zip(questions[start:start+128], vectors[start:start+128])])
                # Only a completed collection gets a manifest; contains public content only.
                path = self.root / (release + ".ready.json")
                temp = path.with_suffix(".tmp")
                temp.write_text(json.dumps({"model": self.settings.EMBEDDING_MODEL, "questions": records}, ensure_ascii=False), encoding="utf-8")
                temp.replace(path)
        except Exception as error:
            logging.getLogger(__name__).warning("questionIndexFailure=%s", type(error).__name__)
            raise

    def search(self, request):
        from qdrant_client import models as m
        if self.status(request.releaseId)["status"] != "READY":
            raise RuntimeError("index not ready")
        manifest = json.loads((self.root / (request.releaseId + ".ready.json")).read_text(encoding="utf-8"))
        public = {q["id"]: SearchQuestion(**q) for q in manifest["questions"]}
        overrides = {q.id: q for q in request.overrides}
        allowed = set(request.allowedIds)
        candidates = {i: overrides.get(i, public.get(i)) for i in allowed}
        candidates = {i: q for i, q in candidates.items() if q is not None}
        if not candidates:
            return {"releaseId": request.releaseId, "matches": [], "total": 0}
        query_vector = self.encode([request.query])[0]
        scores = {}
        indexed = sorted(allowed.intersection(public).difference(overrides))
        if indexed:
            with self.lock:
                hits = self._client().query_points(request.releaseId.replace("-", "_"), query=query_vector,
                    query_filter=m.Filter(must=[m.FieldCondition(key="questionId", match=m.MatchAny(any=indexed))]),
                    limit=len(indexed), score_threshold=self.settings.QUESTION_MIN_SCORE).points
            scores.update({h.payload["questionId"]: float(h.score) for h in hits})
        if overrides:
            historical = list(overrides.values())
            for q, vector in zip(historical, self.encode([q.text() for q in historical])):
                score = cosine(query_vector, vector)
                if score >= self.settings.QUESTION_MIN_SCORE:
                    scores[q.id] = score
        matches = []
        for i, q in candidates.items():
            label = topic_matches(request.query, q.knowledgePoint)
            if label or i in scores and not conflicts_with_topic(request.query, q):
                matches.append({"id": i, "version": q.version, "method": "LABEL" if label else "SEMANTIC", "score": scores.get(i)})
        matches.sort(key=lambda r: (r["method"] != "LABEL", -(r["score"] or 0), r["id"]))
        return {"releaseId": request.releaseId, "matches": matches, "total": len(matches)}

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=True)
        if self.client:
            self.client.close()
