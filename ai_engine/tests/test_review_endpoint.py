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
