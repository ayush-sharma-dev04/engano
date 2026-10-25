"""The proxy the site-rendering browser goes through must never reach non-public addresses."""

import asyncio

import pytest

from engano_backend.safe_proxy import SafeProxy

PUBLIC = "93.184.216.34"


async def talk(port: int, payload: bytes) -> bytes:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(payload)
    await writer.drain()
    data = await asyncio.wait_for(reader.read(65536), 5)
    writer.close()
    return data


def run(coro):
    return asyncio.run(coro)


def make(mapping=None, allow=lambda ip: False):
    async def resolve(host):
        return (mapping or {}).get(host, [PUBLIC])
    return SafeProxy(resolve=resolve, is_public=allow)


async def refused(proxy: SafeProxy, request: bytes) -> bytes:
    port = await proxy.start()
    try:
        return await talk(port, request)
    finally:
        await proxy.stop()


@pytest.mark.parametrize("target", [
    "127.0.0.1:443", "localhost:443", "10.0.0.5:80", "169.254.169.254:80", "192.168.1.1:443", "[::1]:443",
])
def test_connect_to_internal_addresses_is_refused(target):
    proxy = SafeProxy(resolve=lambda h: asyncio.sleep(0, ["127.0.0.1"]))
    reply = run(refused(proxy, f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode()))
    assert reply.startswith(b"HTTP/1.1 403")


def test_a_public_name_that_resolves_to_a_private_address_is_refused():
    proxy = make({"rebind.example": ["10.1.2.3"]}, allow=lambda ip: ip == PUBLIC)
    reply = run(refused(proxy, b"CONNECT rebind.example:443 HTTP/1.1\r\n\r\n"))
    assert reply.startswith(b"HTTP/1.1 403") and proxy.refused == ["rebind.example"]


def test_mixed_public_and_private_addresses_are_refused():
    proxy = make({"mixed.example": [PUBLIC, "127.0.0.1"]}, allow=lambda ip: ip == PUBLIC)
    assert run(refused(proxy, b"CONNECT mixed.example:443 HTTP/1.1\r\n\r\n")).startswith(b"HTTP/1.1 403")


@pytest.mark.parametrize("port", [22, 25, 8080, 6379])
def test_only_web_ports_are_allowed(port):
    proxy = make(allow=lambda ip: True)
    assert run(refused(proxy, f"CONNECT example.com:{port} HTTP/1.1\r\n\r\n".encode())).startswith(b"HTTP/1.1 403")


def test_plain_http_to_an_internal_address_is_refused():
    proxy = SafeProxy(resolve=lambda h: asyncio.sleep(0, ["127.0.0.1"]))
    assert run(refused(proxy, b"GET http://127.0.0.1/admin HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")).startswith(b"HTTP/1.1 403")


def test_garbage_is_ignored_without_crashing():
    proxy = make()
    assert run(refused(proxy, b"not a proxy request\r\n\r\n")) in (b"", b"HTTP/1.1 400 bad request\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")


def test_allowed_public_traffic_is_forwarded_and_proxy_headers_are_stripped():
    """With the safety check relaxed for a local test server, requests really pass through."""

    async def scenario():
        seen = {}

        async def origin(reader, writer):
            seen["request"] = await reader.readuntil(b"\r\n\r\n")
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nhi")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(origin, "127.0.0.1", 0)
        origin_port = server.sockets[0].getsockname()[1]
        proxy = SafeProxy(
            resolve=lambda h: asyncio.sleep(0, ["127.0.0.1"]),
            is_public=lambda ip: True,
            allowed_ports=frozenset({origin_port}),
        )
        port = await proxy.start()
        try:
            reply = await talk(
                port,
                f"GET http://site.test:{origin_port}/a?b=1 HTTP/1.1\r\nHost: site.test\r\nProxy-Connection: keep-alive\r\n\r\n".encode(),
            )
        finally:
            await proxy.stop()
            server.close()
        return reply, seen["request"]

    reply, forwarded = run(scenario())
    assert reply.endswith(b"hi") and reply.startswith(b"HTTP/1.1 200")
    assert forwarded.startswith(b"GET /a?b=1 HTTP/1.1\r\n") and b"Proxy-" not in forwarded


def test_non_standard_ports_are_refused_even_for_public_hosts():
    proxy = make(allow=lambda ip: True)
    assert run(refused(proxy, b"GET http://example.com:8080/ HTTP/1.1\r\nHost: example.com\r\n\r\n")).startswith(b"HTTP/1.1 403")
