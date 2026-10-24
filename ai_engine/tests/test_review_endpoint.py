"""POST /api/review: the endpoint the web studio calls."""

import pytest
from starlette.testclient import TestClient

from ai_engine.config import EngineConfig
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.memory.store import FileBrandMemoryStore
from engano_backend.app import create_app
from engano_backend.review_service import ReviewService, ReviewSettings

FIXTURE = "data/brand_library/nimbus_db.json"
ORIGIN = "http://localhost:5173"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    repo = MockPolicyRepository()
    repo.load_fixture(FIXTURE)
    service = ReviewService(
        ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"),
        repository=repo,
        memory_store=FileBrandMemoryStore(storage_dir=tmp_path),
    )
    return TestClient(create_app(review_service=service, engine_config=EngineConfig()))


def test_review_returns_decision_findings_and_rewrite(client):
    r = client.post("/api/review", json={"text": "NimbusDB has 100% uptime. Try it free forever."})
    assert r.status_code == 200
    body = r.json()
    assert body["decision"]["status"] == "RED"
    cats = {f["category"] for f in body["findings"]}
    assert {"terminology", "wrong_fact", "outdated_offer"} <= cats
    assert body["proposed_rewrite"]


def test_clean_draft_is_green(client):
    r = client.post("/api/review", json={"text": "Nimbus DB is a reliable platform for modern teams."})
    assert r.status_code == 200
    assert r.json()["decision"]["status"] == "GREEN"
    assert r.json()["findings"] == []


@pytest.mark.parametrize("body", [{}, {"text": ""}, {"text": "x" * 10_001}])
def test_invalid_bodies_rejected(client, body):
    assert client.post("/api/review", json=body).status_code == 422


def test_whitespace_only_rejected(client):
    assert client.post("/api/review", json={"text": "   "}).status_code == 422


def test_client_cannot_choose_the_brand(client):
    r = client.post("/api/review", json={"text": "Hello", "brand_id": "someone_else"})
    assert r.status_code == 200
    assert r.json()["brand_id"] == "nimbus_cloud"


def test_cors_allows_studio_origin_only(client):
    ok = client.options(
        "/api/review",
        headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )
    assert ok.headers.get("access-control-allow-origin") == ORIGIN
    bad = client.options(
        "/api/review",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in bad.headers


def test_provider_findings_quoting_text_not_in_draft_are_dropped(tmp_path):
    """A small LLM once reported findings on the policy's sample draft instead of the real one."""
    from ai_engine.agents.coordinator import CoordinatorAgent
    from ai_engine.providers.base import BaseProvider, ProviderResponse
    from ai_engine.schemas.findings import EvidenceStatus, Finding, FindingCategory, FindingSeverity, TextSpan
    from ai_engine.schemas.review import ReviewInput

    def finding(text):
        return Finding(
            finding_id="x", category=FindingCategory.TONE_MISMATCH, severity=FindingSeverity.HIGH,
            highlighted_text=text, text_span=TextSpan(start=0, end=len(text)), explanation="e",
            evidence_status=EvidenceStatus.UNSUPPORTED, cited_source="Rule 3.1", suggested_fix=None,
            human_review_required=True,
        )

    class Liar(BaseProvider):
        provider_name = "liar"

        def review(self, content_text, policy, deterministic_findings, images=None, context=None):
            return ProviderResponse(provider_name="liar", findings=[finding("NimbusDB is the fastest database"), finding("great  workouts")])

    repo = MockPolicyRepository()
    repo.load_fixture(FIXTURE)
    agent = CoordinatorAgent(repo, config=EngineConfig(), provider=Liar(), retriever=None)
    result = agent.run_review(ReviewInput(draft_id="d", brand_id="nimbus_cloud", content_text="We make Great workouts fun."))
    quotes = [f.highlighted_text for f in result.findings]
    assert "NimbusDB is the fastest database" not in quotes
    assert "great  workouts" in quotes  # real quote, whitespace/case differences tolerated


def test_llm_findings_are_advisory_never_high_or_critical():
    from ai_engine.agents.coordinator import CoordinatorAgent
    from ai_engine.providers.base import BaseProvider, ProviderResponse
    from ai_engine.schemas.findings import EvidenceStatus, Finding, FindingCategory, FindingSeverity, TextSpan

    class Loud(BaseProvider):
        provider_name = "loud"

        def review(self, content_text, policy, deterministic_findings, images=None, context=None):
            q = "workouts"
            return ProviderResponse(provider_name="loud", findings=[Finding(
                finding_id="x", category=FindingCategory.TONE_MISMATCH, severity=FindingSeverity.CRITICAL,
                highlighted_text=q, text_span=TextSpan(start=0, end=len(q)), explanation="e",
                evidence_status=EvidenceStatus.VERIFIED, cited_source="Rule 3.1", suggested_fix=None,
                human_review_required=False)])

    from ai_engine.schemas.review import ReviewInput
    repo = MockPolicyRepository()
    repo.load_fixture(FIXTURE)
    agent = CoordinatorAgent(repo, config=EngineConfig(), provider=Loud(), retriever=None)
    result = agent.run_review(ReviewInput(draft_id="d", brand_id="nimbus_cloud", content_text="Great workouts."))
    llm = [f for f in result.findings if f.cited_source == "Rule 3.1"]
    assert llm and llm[0].severity.value == "medium" and llm[0].human_review_required
    assert result.decision.status.value != "RED"


def test_llm_finding_citing_no_policy_rule_is_dropped():
    from ai_engine.agents.coordinator import CoordinatorAgent
    from ai_engine.providers.base import BaseProvider, ProviderResponse
    from ai_engine.schemas.findings import EvidenceStatus, Finding, FindingCategory, FindingSeverity, TextSpan
    from ai_engine.schemas.review import ReviewInput

    class Vague(BaseProvider):
        provider_name = "vague"

        def review(self, content_text, policy, deterministic_findings, images=None, context=None):
            return ProviderResponse(provider_name="vague", findings=[Finding(
                finding_id="x", category=FindingCategory.TONE_MISMATCH, severity=FindingSeverity.MEDIUM,
                highlighted_text="workouts", text_span=TextSpan(start=0, end=8), explanation="feels off",
                evidence_status=EvidenceStatus.VERIFIED, cited_source=None, suggested_fix=None,
                human_review_required=False)])

    repo = MockPolicyRepository()
    repo.load_fixture(FIXTURE)
    agent = CoordinatorAgent(repo, config=EngineConfig(), provider=Vague(), retriever=None)
    result = agent.run_review(ReviewInput(draft_id="d", brand_id="nimbus_cloud", content_text="Great workouts."))
    assert result.findings == [] and result.decision.status.value == "GREEN"
