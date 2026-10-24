"""Website checks through the Docker renderer: the backend treats its answer as untrusted data."""

import asyncio
import base64
import importlib.util
import sys
from pathlib import Path

import httpx
import pytest
from starlette.testclient import TestClient

from engano_backend import site_render
from engano_backend.site_render import RenderedSite, _render_remote, render_site
from engano_backend.website import SiteError

PNG = base64.b64encode(b"\x89PNG-fake").decode()
GOOD = {"final_url": "https://acme.example/", "title": "Acme", "text": "Hello", "screenshots": [PNG, PNG],
        "facts": {"h1": 1}}


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def remote(handler, url="https://acme.example"):
    return asyncio.run(_render_remote("http://renderer:8090", url, client(handler)))


def test_a_good_answer_becomes_a_rendered_site():
    seen = {}

    def handler(request):
        seen["body"] = request.read()
        return httpx.Response(200, json=GOOD)

    site = remote(handler)
    assert site.final_url == "https://acme.example/" and site.title == "Acme" and site.facts == {"h1": 1}
    assert site.screenshots == [b"\x89PNG-fake"] * 2 and b"acme.example" in seen["body"]


def test_the_renderers_refusals_reach_the_creator_in_plain_words():
    with pytest.raises(SiteError, match="isn't a public website"):
        remote(lambda r: httpx.Response(422, json={"detail": "that address isn't a public website"}))


@pytest.mark.parametrize("response", [
    httpx.Response(500, text="boom"),
    httpx.Response(200, json={"final_url": "x"}),                                        # missing fields
    httpx.Response(200, json={**GOOD, "screenshots": ["!!not base64!!"]}),
    httpx.Response(200, text="<html>not json</html>"),
])
def test_bad_answers_never_crash_or_leak_internals(response):
    with pytest.raises(SiteError) as err:
        remote(lambda r: response)
    assert "Traceback" not in str(err.value) and "boom" not in str(err.value)


def test_a_stopped_renderer_says_how_to_start_it():
    def refuse(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(SiteError, match="make renderer"):
        remote(refuse)


def test_oversized_answers_are_trimmed():
    huge = {**GOOD, "text": "x" * 500_000, "title": "t" * 5000, "screenshots": [PNG] * 9}
    site = remote(lambda r: httpx.Response(200, json=huge))
    assert len(site.text) <= site_render.MAX_TEXT_CHARS and len(site.title) <= 300 and len(site.screenshots) <= 3


def test_the_backend_still_refuses_internal_addresses_before_calling_the_renderer(monkeypatch):
    monkeypatch.setenv("ENGANO_RENDERER_URL", "http://renderer:8090")
    called = []

    async def spy(*a, **k):
        called.append(1)

    monkeypatch.setattr(site_render, "_render_remote", spy)
    for url in ("http://127.0.0.1", "http://169.254.169.254/latest", "http://localhost"):
        with pytest.raises(SiteError):
            asyncio.run(render_site(url))
    assert called == []


def test_remote_mode_is_used_when_configured(monkeypatch):
    monkeypatch.setenv("ENGANO_RENDERER_URL", "http://renderer:8090/")
    got = {}

    async def fake_remote(base, url, client=None):
        got.update(base=base, url=url)
        return RenderedSite(final_url=url, title="t", text="x")

    async def public(url, resolve, is_public=None):
        return None

    monkeypatch.setattr(site_render, "_render_remote", fake_remote)
    monkeypatch.setattr(site_render, "_check_public", public)
    asyncio.run(render_site("acme.example"))
    assert got == {"base": "http://renderer:8090", "url": "https://acme.example"}


# ------------------------------------------------------------------ the service inside the container


@pytest.fixture
def service(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "Renderer" / "renderer_app.py"
    spec = importlib.util.spec_from_file_location("renderer_app_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["renderer_app_under_test"] = module
    spec.loader.exec_module(module)
    return module


def test_service_returns_the_render_and_maps_refusals(service, monkeypatch):
    async def ok(url):
        return RenderedSite(final_url=url, title="T", text="body", screenshots=[b"png"], facts={"h1": 1})

    async def refuse(url):
        raise SiteError("that address isn't a public website")

    web = TestClient(service.app)
    monkeypatch.setattr(service, "render_site", ok)
    body = web.post("/render", json={"url": "https://a.example"}).json()
    assert body["title"] == "T" and base64.b64decode(body["screenshots"][0]) == b"png"
    monkeypatch.setattr(service, "render_site", refuse)
    r = web.post("/render", json={"url": "http://10.0.0.1"})
    assert r.status_code == 422 and "public website" in r.json()["detail"]
    assert web.get("/health").json() == {"status": "ok"}
    assert web.get("/docs").status_code == 404


def test_service_token_is_enforced_when_set(service, monkeypatch):
    async def ok(url):
        return RenderedSite(final_url=url, title="T", text="b")

    monkeypatch.setattr(service, "render_site", ok)
    monkeypatch.setattr(service, "TOKEN", "s3cret")
    web = TestClient(service.app)
    assert web.post("/render", json={"url": "https://a.example"}).status_code == 401
    assert web.post("/render", json={"url": "https://a.example"}, headers={"X-Renderer-Token": "wrong"}).status_code == 401
    assert web.post("/render", json={"url": "https://a.example"}, headers={"X-Renderer-Token": "s3cret"}).status_code == 200
