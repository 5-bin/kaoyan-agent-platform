"""Source policy regressions: local files only, no model/index/network calls."""
import hashlib
import json
import runpy
from pathlib import Path
from unittest.mock import Mock

import pytest
import config
import retrieval
from config import Settings, ROOT
from main import create_app
from retrieval import Corpus
from source_policy import ReferenceSourcePolicy, DEFAULT_SOURCE_POLICY


def write_policy(tmp_path, value):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.mark.parametrize("filename", ["corpus.json", "real-corpus-20261024-a476bf509577d904.json"])
def test_entire_corpus_uses_shared_allowlist_without_changing_release(filename):
    path = ROOT / "knowledge" / filename
    corpus = Corpus(path)
    policy = ReferenceSourcePolicy()
    for chunk in corpus.chunks:
        policy.validate_url(chunk.reference().url)
    canonical = json.dumps(json.loads(path.read_text()), ensure_ascii=False,
                           sort_keys=True, separators=(",", ":")).encode()
    assert corpus.release_id == "rag-v1-" + hashlib.sha256(canonical).hexdigest()[:16]
    assert DEFAULT_SOURCE_POLICY.is_file()


def test_exact_host_case_normalization_and_no_implicit_subdomains(tmp_path):
    policy = ReferenceSourcePolicy(write_policy(tmp_path, {"allowedHosts": ["GITHUB.COM"]}))
    policy.validate_url("https://GitHub.Com/example/book")
    for url in ("https://github.com.attacker.invalid/x", "https://sub.github.com/x",
                "https://ocw.mit.edu/x"):
        with pytest.raises(ValueError, match="^SOURCE_HOST_NOT_ALLOWED$"):
            policy.validate_url(url)


@pytest.mark.parametrize("url", ["http://github.com/x", "javascript:alert(1)", "https:///x",
    "https://user@github.com/x", "https://github.com:invalid/x", "https://github.com:65536/x",
    "https://github.com:0/x", "https://github.com/\nsecret"])
def test_malformed_or_credentialed_source_is_rejected(url):
    with pytest.raises(ValueError, match="^INVALID_SOURCE_URL$"):
        ReferenceSourcePolicy().validate_url(url)


@pytest.mark.parametrize("value", [None, [], {}, {"allowedHosts": []}, {"allowedHosts": "github.com"},
    {"allowedHosts": [None]}, {"allowedHosts": ["*.github.com"]},
    {"allowedHosts": ["https://github.com"]}, {"allowedHosts": ["github.com:443"]},
    {"allowedHosts": [" github.com"]}, {"allowedHosts": ["-github.com"]},
    {"allowedHosts": ["github.com"], "unknown": "private-marker"}])
def test_invalid_policy_is_sanitized(tmp_path, value):
    with pytest.raises(ValueError, match="^SOURCE_POLICY_INVALID$"):
        ReferenceSourcePolicy(write_policy(tmp_path, value))


def test_missing_malformed_and_relative_policy_never_fall_back(tmp_path, monkeypatch):
    broken = tmp_path / "broken.json"
    broken.write_text("private-marker", encoding="utf-8")
    for path in (tmp_path / "missing.json", broken, Path("relative.json")):
        with pytest.raises(ValueError, match="^SOURCE_POLICY_INVALID$"):
            ReferenceSourcePolicy(path)
    broken.write_text('{"allowedHosts":["github.com"]} {}', encoding="utf-8")
    with pytest.raises(ValueError, match="^SOURCE_POLICY_INVALID$"):
        ReferenceSourcePolicy(broken)
    monkeypatch.setenv("RAG_SOURCE_POLICY_FILE", str(broken))
    with pytest.raises(ValueError, match="^SOURCE_POLICY_INVALID$"):
        Corpus(ROOT / "knowledge/corpus.json")


def test_startup_and_ingest_reject_unapproved_corpus_before_index_creation(tmp_path, monkeypatch):
    policy = write_policy(tmp_path, {"allowedHosts": ["github.com"]})
    settings = Settings(_env_file=None, AGENT_INTERNAL_KEY="test-only-internal-key-123456",
                        RAG_SOURCE_POLICY_FILE=policy, LLM_ENABLED=False)
    with pytest.raises(ValueError, match="^SOURCE_HOST_NOT_ALLOWED$"):
        create_app(settings)
    monkeypatch.setattr(config, "Settings", lambda: settings)
    index = Mock()
    monkeypatch.setattr(retrieval, "VectorIndex", index)
    with pytest.raises(ValueError, match="^SOURCE_HOST_NOT_ALLOWED$"):
        runpy.run_path(str(ROOT / "ingest.py"), run_name="__main__")
    index.assert_not_called()


def test_external_policy_is_honored_for_valid_corpus_and_relative_setting_rejected(tmp_path):
    records = json.loads((ROOT / "knowledge/corpus.json").read_text())[:1]
    records[0]["url"] = "https://fixture.invalid/approved"
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(ValueError, match="^SOURCE_HOST_NOT_ALLOWED$"):
        Corpus(path)
    policy = write_policy(tmp_path, {"allowedHosts": ["fixture.invalid"]})
    assert len(Corpus(path, policy).documents) == 1
    with pytest.raises(ValueError, match="SOURCE_POLICY_INVALID"):
        Settings(_env_file=None, RAG_SOURCE_POLICY_FILE="relative.json")
