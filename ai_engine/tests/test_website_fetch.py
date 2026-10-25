"""The website reader must never be talked into reading anything but a public web page."""

import asyncio

import httpx
import pytest

from engano_backend.website import SiteError, fetch_site_text, normalize_url

PUBLIC = "93.184.216.34"


def resolver(mapping):
    async def resolve(host):
        return mapping.get(host, [PUBLIC])
    return resolve


def run(coro):
    return asyncio.run(coro)


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def page(html="<html><head><title>Acme</title></head><body><p>Hello world</p></body></html>", kind="text/html"):
    return lambda request: httpx.Response(200, text=html, headers={"content-type": kind})


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com", "javascript:alert(1)", "",
    "https://user:secret@example.com", "https://example.com:8080", "https://example.com:22",
])
def test_unsupported_addresses_are_refused(url):
    with pytest.raises(SiteError):
        normalize_url(url)


@pytest.mark.parametrize("host", [
    "127.0.0.1", "localhost", "10.0.0.5", "192.168.1.10", "172.16.0.9",
    "169.254.169.254", "[::1]", "0.0.0.0",
])
def test_private_and_internal_hosts_are_refused(host):
    mapping = {"localhost": ["127.0.0.1"]}
    with pytest.raises(SiteError, match="public website"):
        run(fetch_site_text(f"http://{host}/x", client=client(page()), resolve=resolver(mapping)))


def test_a_name_that_resolves_to_a_private_address_is_refused():
    with pytest.raises(SiteError, match="public website"):
        run(fetch_site_text("https://evil.example", client=client(page()), resolve=resolver({"evil.example": ["10.1.2.3"]})))


def test_a_name_with_one_private_address_among_public_ones_is_refused():
    with pytest.raises(SiteError):
        run(fetch_site_text("https://mixed.example", client=client(page()), resolve=resolver({"mixed.example": [PUBLIC, "127.0.0.1"]})))


def test_redirect_to_an_internal_address_is_refused():
    def handler(request):
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})
    with pytest.raises(SiteError, match="public website"):
        run(fetch_site_text("https://example.com", client=client(handler), resolve=resolver({})))


def test_redirect_loops_stop():
    def handler(request):
        return httpx.Response(302, headers={"location": "https://example.com/again"})
    with pytest.raises(SiteError, match="too many"):
        run(fetch_site_text("https://example.com", client=client(handler), resolve=resolver({})))


def test_public_page_is_read_and_scripts_are_ignored():
    html = (
        "<html><head><title>Acme Hosting</title><meta name='description' content='Fast servers'>"
        "<script>stealCookies()</script><style>p{}</style></head>"
        "<body><h1>Welcome</h1><p>We host <b>games</b>.</p><script>x()</script></body></html>"
    )
    url, text = run(fetch_site_text("example.com", client=client(page(html)), resolve=resolver({})))
    assert url == "https://example.com"
    assert "Acme Hosting" in text and "Fast servers" in text and "We host games." in text
    assert "stealCookies" not in text and "x()" not in text


def test_non_web_pages_and_errors_are_refused():
    with pytest.raises(SiteError, match="isn't a web page"):
        run(fetch_site_text("https://example.com/a.pdf", client=client(page("%PDF", "application/pdf")), resolve=resolver({})))
    with pytest.raises(SiteError, match="error"):
        run(fetch_site_text("https://example.com", client=client(lambda r: httpx.Response(404)), resolve=resolver({})))


def test_huge_pages_are_cut_off():
    big = "<html><body>" + ("word " * 400_000) + "</body></html>"
    _, text = run(fetch_site_text("https://example.com", client=client(page(big)), resolve=resolver({})))
    assert len(text) <= 20_000
