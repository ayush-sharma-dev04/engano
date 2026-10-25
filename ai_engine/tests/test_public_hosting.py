"""Running the backend on a laptop while the web app is hosted elsewhere (Netlify): who may call it."""

import pytest
from starlette.testclient import TestClient

from ai_engine.config import EngineConfig
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.memory.store import FileBrandMemoryStore
from engano_backend.app import create_app
from engano_backend.review_service import ReviewService, ReviewSettings
from engano_backend.team_store import TeamStore

PW = "password123"
SITE = "https://my-site.netlify.app"


def build(tmp_path, monkeypatch, **env):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    repo = MockPolicyRepository()
    repo.load_fixture("data/brand_library/nimbus_db.json")
    service = ReviewService(
        ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"),
        repository=repo,
        memory_store=FileBrandMemoryStore(storage_dir=tmp_path),
    )
    return TestClient(create_app(review_service=service, engine_config=EngineConfig(), team_store=TeamStore(tmp_path / "t.db")))


def signed_up(client, name):
    r = client.post("/api/auth/signup", json={"name": name, "email": f"{name.lower()}@x.com", "password": PW, "purpose": "Content Creator"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_the_heavy_endpoints_need_a_signed_in_person(tmp_path, monkeypatch):
    c = build(tmp_path, monkeypatch, ENGANO_REQUIRE_LOGIN="1")
    r = c.post("/api/review", json={"text": "Hello there."})
    assert (r.status_code, r.json()["detail"]) == (401, "Sign in to run reviews.")
    assert c.post("/api/check-website", json={"url": "https://example.com"}).status_code == 401
    kate = signed_up(c, "Kate")
    assert c.post("/api/review", json={"text": "Hello there."}, headers=kate).status_code == 200
    bad = c.post("/api/review", json={"text": "Hello there."}, headers={"Authorization": "Bearer nonsense"})
    assert bad.status_code == 401


def test_login_is_required_unless_switched_off(tmp_path, monkeypatch):
    monkeypatch.delenv("ENGANO_REQUIRE_LOGIN", raising=False)
    c = build(tmp_path, monkeypatch)  # the setting's default
    # conftest turns it off for the other tests; here we undo that to see the real default
    monkeypatch.delenv("ENGANO_REQUIRE_LOGIN", raising=False)
    assert c.post("/api/review", json={"text": "Hi."}).status_code == 401


def test_each_person_gets_a_fair_share(tmp_path, monkeypatch):
    c = build(tmp_path, monkeypatch, ENGANO_REQUIRE_LOGIN="1", ENGANO_REVIEW_LIMIT="2")
    kate, rob = signed_up(c, "Kate"), signed_up(c, "Rob")
    codes = [c.post("/api/review", json={"text": "Hello there."}, headers=kate).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert c.post("/api/review", json={"text": "Hello there."}, headers=rob).status_code == 200
    assert "wait a few minutes" in c.post("/api/review", json={"text": "x"}, headers=kate).json()["detail"].lower()


def test_a_hosted_site_may_call_the_backend_only_if_allowed(tmp_path, monkeypatch):
    c = build(tmp_path, monkeypatch, ENGANO_CORS_ORIGIN_REGEX=r"https://[a-z0-9-]+\.netlify\.app")
    ask = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"}
    ok = c.options("/api/app/state", headers={"Origin": SITE, **ask})
    assert ok.headers.get("access-control-allow-origin") == SITE
    assert "authorization" in ok.headers.get("access-control-allow-headers", "").lower()
    preview = c.options("/api/app/state", headers={"Origin": "https://deploy-preview-3--my-site.netlify.app", **ask})
    assert preview.headers.get("access-control-allow-origin")
    for stranger in ("https://evil.example", "https://netlify.app.evil.example", "http://my-site.netlify.app"):
        assert c.options("/api/app/state", headers={"Origin": stranger, **ask}).headers.get("access-control-allow-origin") is None


def test_an_exact_origin_list_works_too(tmp_path, monkeypatch):
    c = build(tmp_path, monkeypatch, ENGANO_CORS_ORIGINS=f"http://localhost:5173,{SITE}")
    ask = {"Access-Control-Request-Method": "GET"}
    assert c.options("/api/app/state", headers={"Origin": SITE, **ask}).headers.get("access-control-allow-origin") == SITE
    assert c.options("/api/app/state", headers={"Origin": "https://other.netlify.app", **ask}).headers.get("access-control-allow-origin") is None


def test_the_review_receipt_header_is_readable_by_the_hosted_site(tmp_path, monkeypatch):
    c = build(tmp_path, monkeypatch, ENGANO_REQUIRE_LOGIN="1", ENGANO_CORS_ORIGINS=SITE)
    kate = signed_up(c, "Kate")
    r = c.post("/api/review", json={"text": "Hello there."}, headers={**kate, "Origin": SITE})
    assert "x-review-receipt" in r.headers.get("access-control-expose-headers", "").lower()
