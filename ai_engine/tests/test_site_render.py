"""Rendering a site with a real browser, including a hostile page trying to reach internal services."""

import asyncio

import pytest

from engano_backend import website
from engano_backend.site_render import render_site, renderer_available
from engano_backend.website import SiteError

pytestmark = pytest.mark.skipif(not renderer_available(), reason="playwright not installed")

PAGE = """<!doctype html><html lang="en"><head><title>Acme Hosting</title>
<meta name="description" content="Fast game servers"><style>
.pulse{animation:pulse 2s infinite} @keyframes pulse{from{opacity:.4}to{opacity:1}}
body{font-family:Georgia,serif}</style></head>
<body><h1 class="pulse">Welcome to Acme</h1><p>We host games.</p>
<img src="/x.png" width="200" height="120"><img src="/y.png" alt="" width="50" height="50">
<video autoplay loop width="200" height="100"></video></body></html>"""

HOSTILE = """<!doctype html><title>x</title><h1>hi</h1><script>
const targets = ["http://127.0.0.1:%(secret)d/secret", "http://localhost:%(secret)d/secret", "http://[::1]:%(secret)d/s"];
for (const t of targets) { fetch(t, {mode: "no-cors"}).catch(() => {}); try { new WebSocket(t.replace("http", "ws")) } catch (e) {} }
const i = new Image(); i.src = "http://127.0.0.1:%(secret)d/pixel.png";
</script>"""


async def serve(body: str, host: str):
    async def handle(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        data = body.encode()
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(data) + data)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, host, 0)
    return server, server.sockets[0].getsockname()[1]


def only_loopback_2(ip: str) -> bool:  # in this test, 127.0.0.2 plays "the public internet"
    return ip == "127.0.0.2"


def test_real_page_is_rendered_and_measured(monkeypatch):
    async def scenario():
        server, port = await serve(PAGE, "127.0.0.2")
        monkeypatch.setattr(website, "ALLOWED_PORTS", {None, 80, 443, port})
        try:
            async def resolve(host):
                return ["127.0.0.2"]
            return await render_site(f"http://acme.test:{port}/", resolve=resolve, is_public=only_loopback_2, allowed_ports=frozenset({port}))
        finally:
            server.close()

    site = asyncio.run(scenario())
    f = site.facts
    assert site.title == "Acme Hosting" and "We host games." in site.text and site.screenshots
    assert f["h1"] == 1 and f["description"] == "Fast game servers" and f["lang"] == "en" and f["viewportMeta"] is False
    assert f["images"] == 2 and f["imagesMissingAlt"] == 1          # alt="" is a deliberate decorative image
    assert f["animatedElements"] >= 1 and f["reducedMotionSupport"] is False
    assert f["autoplayMovingNoControls"] == 1
    assert "Georgia" in f["fonts"]


def test_hostile_page_cannot_reach_internal_services(monkeypatch):
    async def scenario():
        hits = []

        async def secret(reader, writer):
            hits.append(await reader.read(100))
            writer.close()

        secret_server = await asyncio.start_server(secret, "127.0.0.1", 0)
        secret_port = secret_server.sockets[0].getsockname()[1]
        origin, port = await serve(HOSTILE % {"secret": secret_port}, "127.0.0.2")
        monkeypatch.setattr(website, "ALLOWED_PORTS", {None, 80, 443, port})
        try:
            async def resolve(host):
                return ["127.0.0.2"] if host == "evil.test" else ["127.0.0.1"]
            site = await render_site(
                f"http://evil.test:{port}/", resolve=resolve, is_public=only_loopback_2,
                allowed_ports=frozenset({port, secret_port}),  # ports are NOT the defence here: the address check is
            )
            await asyncio.sleep(0.5)
            return site, hits
        finally:
            origin.close()
            secret_server.close()

    site, hits = asyncio.run(scenario())
    assert "hi" in site.text
    assert hits == [], "the page's JavaScript reached an internal service through the browser"


def test_internal_targets_are_refused_up_front():
    for url in ("http://127.0.0.1", "http://localhost", "http://169.254.169.254/latest", "http://10.0.0.1", "file:///etc/passwd"):
        with pytest.raises(SiteError):
            asyncio.run(render_site(url))
