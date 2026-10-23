"""LinkedIn adapter tests: real ai_engine + Nimbus fixture, fake LinkedIn API."""

import time

import httpx
import pytest
from fastapi.testclient import TestClient

from engano_backend.app import create_app
from engano_backend.review_service import ReviewService, ReviewSettings
from engano_linkedin.client import LinkedInClient, escape_commentary
from engano_linkedin.config import LinkedInSettings
from engano_linkedin.token_store import LinkedInToken, TokenStore
from engano_whatsapp.config import WhatsAppSettings

CLEAN_POST = "Nimbus DB keeps your data safe with a 99.95% uptime SLA."
BAD_POST = "NimbusDB is the fastest database in the world, with 100% uptime. Try it free forever!"


class FakeLinkedIn:
    """Stands in for www.linkedin.com and api.linkedin.com."""

    def __init__(self):
        self.posts: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/v2/accessToken":
            return httpx.Response(200, json={"access_token": "li-token", "expires_in": 5184000})
        if request.url.path == "/v2/userinfo":
            return httpx.Response(200, json={"sub": "abc123", "name": "Sankhyahrick Swami"})
        if request.url.path == "/rest/posts":
            self.posts.append({"headers": dict(request.headers), "body": request.read().decode()})
            return httpx.Response(201, headers={"x-restli-id": "urn:li:share:999"})
        return httpx.Response(404)


@pytest.fixture
def linkedin():
    return FakeLinkedIn()


@pytest.fixture
def store(tmp_path):
    return TokenStore(tmp_path / "token.json")


@pytest.fixture
def client(linkedin, store):
    settings = LinkedInSettings(client_id="id", client_secret="secret")
    li_client = LinkedInClient(settings, httpx.AsyncClient(transport=httpx.MockTransport(linkedin.handler)))
    app = create_app(
        ReviewService(ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture")),
        WhatsAppSettings(access_token=None, app_secret=None, verify_token=None),
        None,
        settings,
        li_client,
        store,
    )
    with TestClient(app) as c:
        yield c


def connect(client) -> None:
    start = client.get("/api/oauth/linkedin/start", follow_redirects=False)
    assert start.status_code == 307
    location = httpx.URL(start.headers["location"])
    assert location.host == "www.linkedin.com"
    assert "w_member_social" in location.params["scope"]
    done = client.get("/api/oauth/linkedin/callback", params={"code": "c0de", "state": location.params["state"]})
    assert done.status_code == 200 and "Sankhyahrick Swami" in done.text


def test_connect_flow_saves_token(client, store):
    assert client.get("/api/linkedin/status").json()["connected"] is False
    connect(client)
    status = client.get("/api/linkedin/status").json()
    assert status["connected"] is True and status["posts_as"] == "urn:li:person:abc123"
    assert (store.path.stat().st_mode & 0o777) == 0o600


def test_callback_rejects_unknown_state(client):
    assert client.get("/api/oauth/linkedin/callback", params={"code": "x", "state": "forged"}).status_code == 400


def test_check_never_publishes(client, linkedin):
    review = client.post("/api/linkedin/check", json={"text": BAD_POST}).json()
    assert review["decision"]["status"] == "RED" and linkedin.posts == []


def test_publish_requires_connection(client):
    resp = client.post("/api/linkedin/publish", json={"text": CLEAN_POST, "approved_by": "Ayush"})
    assert resp.status_code == 409


def test_publish_requires_approver(client):
    connect(client)
    assert client.post("/api/linkedin/publish", json={"text": CLEAN_POST}).status_code == 422


def test_red_post_is_blocked(client, linkedin):
    connect(client)
    resp = client.post("/api/linkedin/publish", json={"text": BAD_POST, "approved_by": "Ayush"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["review"]["decision"]["status"] == "RED"
    assert linkedin.posts == []


def test_green_approved_post_is_published(client, linkedin):
    connect(client)
    resp = client.post("/api/linkedin/publish", json={"text": CLEAN_POST, "approved_by": "Ayush"})
    assert resp.status_code == 200
    assert resp.json()["post_urn"] == "urn:li:share:999"
    [post] = linkedin.posts
    assert post["headers"]["linkedin-version"] == "202608"
    assert '"author":"urn:li:person:abc123"' in post["body"].replace(" ", "")


def test_expired_token_counts_as_disconnected(client, store):
    store.save(LinkedInToken("t", time.time() - 10, "urn:li:person:x"))
    assert client.get("/api/linkedin/status").json()["connected"] is False


def test_organization_posts_use_company_urn():
    settings = LinkedInSettings(client_id="id", client_secret="s", organization_id="42")
    assert "w_organization_social" in settings.scopes
    token = LinkedInToken("t", time.time() + 100, "urn:li:person:x")
    assert LinkedInClient(settings).author_urn(token) == "urn:li:organization:42"


def test_little_text_escaping():
    assert escape_commentary("Hi (all) #launch @team") == r"Hi \(all\) \#launch \@team"
