"""Quality-focused tests: BM25/hybrid retrieval, subject hints, citation support."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config import Settings
from grounding import aggregate, verify
from main import create_app
from retrieval import Corpus, Retriever, detect_subject
from schemas import Answer, Claim

KEY = "test-only-internal-key-123456"
HEADERS = {"X-Internal-Key": KEY}
ROOT = Path(__file__).resolve().parents[1]
BASE_CORPUS = ROOT / "knowledge/corpus.json"
PROVIDER = "https://api.deepseek.com"


class FakeModel:
    def __init__(self, response=None, error=False):
        self.response, self.error, self.calls = response, error, 0

    async def generate(self, *args, **kwargs):
        self.calls += 1
        if self.error:
            raise RuntimeError("provider detail must not escape")
        return self.response

    async def close(self):
        pass


def settings(**changes):
    values = {"_env_file": None, "AGENT_INTERNAL_KEY": KEY, "RAG_DATA": BASE_CORPUS,
              "LLM_BASE_URL": PROVIDER}
    values.update(changes)
    return Settings(**values)


def post(client, body):
    response = client.post("/internal/rag/chat", headers=HEADERS, json=body)
    assert response.status_code == 200, response.text
    return response.json()["result"]


def qa_request(query):
    return {"taskId": "quality-task-1", "userId": 1, "taskType": "KNOWLEDGE_QA",
            "userInput": query, "profile": {},
            "privacy": {"modelAllowed": True, "scopes": ["profile"], "provider": PROVIDER}}


def test_bm25_ranks_the_matching_subject_and_can_filter():
    corpus = Corpus(BASE_CORPUS)
    ranked = corpus.bm25("TCP 重传", "knowledge", 5)
    assert ranked and ranked[0].id.startswith("cn-tcp")
    assert corpus.bm25("进程", "knowledge", 5, subject="计算机网络") == []
    # Single common characters must not turn an uncovered topic into a hit.
    assert corpus.bm25("三次握手", "knowledge", 5) == []
    assert corpus.bm25("栈", "knowledge", 5)[0].id.startswith("ds-deque")


@pytest.mark.parametrize("text,expected", [
    ("栈和队列有什么区别", "数据结构"),
    ("进程和线程的区别", "操作系统"),
    ("TCP如何保证可靠传输", "计算机网络"),
    ("主存和虚拟内存", "计算机组成原理"),
    ("海水观赏鱼繁育", None),
])
def test_subject_hint_is_conservative(text, expected):
    assert detect_subject(text) == expected


def test_hybrid_falls_back_to_bm25_without_a_vector_marker(tmp_path):
    config = settings(RAG_BACKEND="hybrid", RAG_INDEX=tmp_path, RAG_MIN_SCORE=0)
    corpus = Corpus(BASE_CORPUS)
    retriever = Retriever(config, corpus)
    try:
        results = retriever.search("TCP 重传", "knowledge", 5)
        assert results and results[0].id.startswith("cn-tcp")
    finally:
        retriever.close()


def test_grounding_supported_and_unsupported_claims():
    corpus = Corpus(BASE_CORPUS)
    chunk = corpus.chunk_by_id["cn-tcp#0"]
    supported = verify("TCP通过序号、确认和重传恢复丢失。", ["cn-tcp#0"], {"cn-tcp#0": chunk})
    assert supported["status"] == "SUPPORTED"
    assert supported["ratio"] == 1.0
    unsupported = verify("TCP使用三次握手建立连接。", ["cn-tcp#0"], {"cn-tcp#0": chunk})
    assert unsupported["status"] == "UNSUPPORTED"
    assert unsupported["unsupported"][0]["reason"] == "low_overlap"
    unknown = verify("TCP通过序号确认恢复丢失。", ["missing#0"], {"cn-tcp#0": chunk})
    assert unknown["unsupported"][0]["reason"] == "unknown_source"
    meta = verify("资料未进一步说明该细节。", ["cn-tcp#0"], {"cn-tcp#0": chunk})
    assert meta["status"] == "NOT_CHECKED"


def test_aggregate_uses_checked_claim_ratio():
    merged = aggregate([
        {"checked": 2, "supported": 2, "unsupported": []},
        {"checked": 1, "supported": 0, "unsupported": [{"text": "x", "reason": "low_overlap"}]},
    ])
    assert merged["checked"] == 3 and merged["supported"] == 2
    assert merged["status"] == "PARTIAL"
    assert merged["unsupported"]


def test_qa_downgrades_an_ungrounded_model_answer():
    model = FakeModel(response=Answer(answer="TCP使用三次握手建立连接。", sourceIds=["cn-tcp#0"]))
    with TestClient(create_app(settings(LLM_ENABLED=True, LLM_API_KEY="test-only"), model=model)) as client:
        result = post(client, qa_request("TCP如何保证可靠传输"))
    assert result["citationSupport"]["status"] == "UNSUPPORTED"
    assert result["explanationMode"] == "fallback"
    assert result["answer"].startswith("以下为来源摘要")


def test_qa_keeps_a_grounded_model_answer_with_support_metadata():
    model = FakeModel(response=Answer(answer="TCP通过序号、确认和重传恢复丢失。", sourceIds=["cn-tcp#0"]))
    with TestClient(create_app(settings(LLM_ENABLED=True, LLM_API_KEY="test-only"), model=model)) as client:
        result = post(client, qa_request("TCP如何保证可靠传输"))
    assert result["explanationMode"] == "ai"
    assert result["citationSupport"]["status"] == "SUPPORTED"
    assert result["references"][0]["id"] == "cn-tcp#0"


def test_qa_verifies_each_claim_against_its_own_source():
    model = FakeModel(response=Answer(
        answer="TCP通过序号、确认和重传恢复丢失。TCP使用三次握手建立连接。",
        sourceIds=["cn-tcp#0"],
        claims=[
            Claim(text="TCP通过序号、确认和重传恢复丢失。", sourceIds=["cn-tcp#0"]),
            Claim(text="TCP使用三次握手建立连接。", sourceIds=["cn-tcp#0"]),
        ]))
    with TestClient(create_app(settings(LLM_ENABLED=True, LLM_API_KEY="test-only"), model=model)) as client:
        result = post(client, qa_request("TCP如何保证可靠传输"))
    support = result["citationSupport"]
    assert result["explanationMode"] == "ai"
    assert support["checked"] == 2 and support["supported"] == 1
    assert support["status"] == "PARTIAL"
    assert support["items"][0]["supported"] is True
    assert support["items"][1]["supported"] is False
    assert support["items"][1]["reason"] == "low_overlap"


def test_qa_rejects_a_claim_citing_an_unknown_source():
    model = FakeModel(response=Answer(
        answer="TCP通过序号、确认和重传恢复丢失。",
        sourceIds=["cn-tcp#0"],
        claims=[Claim(text="TCP通过序号、确认和重传恢复丢失。", sourceIds=["missing#0"])]))
    with TestClient(create_app(settings(LLM_ENABLED=True, LLM_API_KEY="test-only"), model=model)) as client:
        result = post(client, qa_request("TCP如何保证可靠传输"))
    assert result["explanationMode"] == "fallback"
    assert result["answer"].startswith("以下为来源摘要")


def test_subject_filter_falls_back_instead_of_reporting_false_coverage_gap():
    with TestClient(create_app(settings())) as client:
        result = post(client, qa_request("操作系统中的虚拟内存"))
    # The hint points at 操作系统, whose only excerpt lacks this topic; the
    # unfiltered retry still finds the reviewed 组成原理 excerpt.
    assert result["outcome"] == "COMPLETED"
    assert result["references"][0]["id"].startswith("co-memory")
