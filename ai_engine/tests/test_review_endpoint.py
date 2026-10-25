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


def test_answers_flow_through_the_api_and_the_website_is_read(client, monkeypatch):
    seen = {}

    async def fake_fetch(url):
        seen["url"] = url
        return "https://acme.example/", "Nimbus DB is the fastest database in the world, says our homepage."

    monkeypatch.setattr("engano_backend.review_service.fetch_site_text", fake_fetch)
    first = client.post("/api/review", json={"text": "Nimbus DB is the fastest database in the world."}).json()
    assert {q["kind"] for q in first["questions"]} == {"evidence", "website"}

    second = client.post("/api/review", json={
        "text": "Nimbus DB is the fastest database in the world.",
        "answers": {"website": "acme.example"},
    }).json()
    assert seen["url"] == "acme.example"
    assert {q["kind"] for q in second["questions"]} == {"evidence"}
    note = next(f for f in second["findings"] if f["category"] == "unsupported_claim")["explanation"]
    assert "appears on https://acme.example/" in note


def test_unreadable_website_comes_back_as_a_question(client, monkeypatch):
    from engano_backend.website import SiteError

    async def failing(url):
        raise SiteError("that address isn't a public website")

    monkeypatch.setattr("engano_backend.review_service.fetch_site_text", failing)
    body = client.post("/api/review", json={
        "text": "Nimbus DB is the fastest database in the world.", "answers": {"website": "http://10.0.0.1"},
    }).json()
    q = next(q for q in body["questions"] if q["kind"] == "website")
    assert "isn't a public website" in q["text"]


def test_oversized_answers_are_rejected(client):
    assert client.post("/api/review", json={"text": "hi", "answers": {"website": "x" * 2001}}).status_code == 422
    assert client.post("/api/review", json={"text": "hi", "answers": {f"k{i}": "v" for i in range(13)}}).status_code == 422


def _png_b64(text="NimbusDB has 100% uptime"):
    import base64
    import io

    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1100, 220), "white")
    ImageDraw.Draw(img).text((30, 60), text, fill="black", font=ImageFont.load_default(size=56))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_image_only_review_reads_the_text_inside_the_image(client):
    import shutil

    if not shutil.which("tesseract"):
        pytest.skip("tesseract not installed")
    r = client.post("/api/review", json={"images": [{"data": _png_b64(), "alt_text": "A banner"}]})
    assert r.status_code == 200
    body = r.json()
    in_image = [f for f in body["findings"] if f["image_index"] == 1 and f["highlighted_text"].startswith("[Image 1]")]
    assert {"terminology", "wrong_fact"} <= {f["category"] for f in in_image}
    assert body["decision"]["status"] == "RED"


def test_unreadable_images_are_reported_not_rejected(client):
    import base64

    junk = base64.b64encode(b"definitely not an image").decode()
    body = client.post("/api/review", json={"text": "Hello", "images": [{"data": junk}]}).json()
    assert any("could not be checked" in f["explanation"] for f in body["findings"])
    assert body["decision"]["status"] != "GREEN"


def test_image_limits_are_enforced(client):
    one = {"data": "A" * 100}
    assert client.post("/api/review", json={"text": "x", "images": [one] * 5}).status_code == 422
    assert client.post("/api/review", json={"text": "x", "images": [{"data": "A" * 5_600_001}]}).status_code == 422
    assert client.post("/api/review", json={"images": []}).status_code == 422
