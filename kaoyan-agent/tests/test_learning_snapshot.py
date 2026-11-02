import pytest
from core.errors import ModelUnavailable
from tests.test_workflows import client, request, post, FakeModel, HEADERS

SNAPSHOT = dict(profileRevision=3, referenceScore=90.0, coverage=1.0,
                sufficient=True, blueprintVersion="reviewed-v1:1", calibrated=False)


def test_learning_snapshot_preserves_candidates_and_rules_without_model():
    model = FakeModel(error=True)
    with client(model) as c:
        baseline = post(c, request())["result"]
        result = post(c, request(learningSnapshot=SNAPSHOT))["result"]
        assert result["candidates"] == baseline["candidates"]
        assert result["learningSnapshot"] == SNAPSHOT
        assert result["resultSchemaVersion"] == 2
        assert model.calls == 0


@pytest.mark.parametrize("change", [dict(ownerId=2), dict(referenceScore=151),
    dict(referenceScore=-1), dict(coverage=1.1), dict(calibrated=True), dict(profileRevision=-1)])
def test_learning_snapshot_rejects_forged_or_invalid_fields(change):
    with client() as c:
        body = request(learningSnapshot={**SNAPSHOT, **change})
        assert c.post("/internal/rag/chat", headers=HEADERS, json=body).status_code == 422


def test_learning_snapshot_rejected_on_unrelated_task():
    with client() as c:
        body = request("KNOWLEDGE_QA", userInput="进程与线程", learningSnapshot=SNAPSHOT)
        assert c.post("/internal/rag/chat", headers=HEADERS, json=body).status_code == 422


def test_model_projection_withholds_learning_snapshot_without_stats_consent():
    class Capture(FakeModel):
        async def generate(self, prompt, payload, *args, **kwargs):
            assert payload["learningSnapshot"] == {}
            self.calls += 1
            raise ModelUnavailable("test fallback")
    model = Capture()
    with client(model, enabled=True) as c:
        body = request(learningSnapshot=SNAPSHOT)
        body["privacy"]["scopes"] = ["profile"]
        result = post(c, body)["result"]
        assert model.calls == 1
        assert result["explanationMode"] == "fallback"


def test_current_profile_projection_inherits_stats_consent_and_drops_identifiers():
    from schemas import ConversationResolution
    from tests.test_learning_privacy import request as learning_request
    from learning import safe_learning_context, rule_learning_answer
    plan = ConversationResolution(action="LEARNING_ANALYSIS", standaloneQuery="分析学情", reads=["stats"])
    req = learning_request(preparedPlan=plan, privacy={"modelAllowed": True, "scopes": ["stats"]}, learningContext={
        "statistics": {"questionCount": 1, "correctCount": 1, "learningProfile": {
            "revision": 2, "userId": 12345, "referenceScore": None, "independentSamples": 7,
            "groups": [{"knowledgePoint": "树", "difficulty": "HARD", "samples": 7, "anomaly": True, "questionId": 999}]}}})
    projected = safe_learning_context(req)
    assert "userId" not in projected["statistics"]["learningProfile"]
    assert "questionId" not in projected["statistics"]["learningProfile"]["groups"][0]
    assert "近期表现异常" in rule_learning_answer(projected, plan)
    req.privacy.scopes = []
    assert "statistics" not in safe_learning_context(req)
    assert "learningProfile" in safe_learning_context(req, external=False)["statistics"]
