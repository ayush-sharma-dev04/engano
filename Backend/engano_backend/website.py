"""Read a company website the creator pointed us at, without being tricked into
reading anything else.

The address comes from an untrusted person, so before every request (and every redirect)
we check that it is plain http(s) on a standard port, has no embedded login, and resolves
only to public internet addresses. Private, loopback, link-local and cloud-metadata
addresses are refused. Responses are size- and time-limited and only HTML or text is read.

The page text is used as context for the reviewer. It is never put into an AI prompt.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from html.parser import HTMLParser
from typing import Awaitable, Callable, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

import httpx

MAX_BYTES = 1_500_000
MAX_TEXT_CHARS = 20_000
MAX_REDIRECTS = 3
ALLOWED_PORTS = {None, 80, 443}
USER_AGENT = "ENGANO-brand-check/0.1 (+reads a page the creator submitted)"

Resolver = Callable[[str], Awaitable[List[str]]]


class SiteError(Exception):
    """The site could not be read. The message is safe to show to the creator."""


async def system_resolver(host: str) -> List[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise SiteError("that address doesn't exist") from None
    return sorted({info[4][0] for info in infos})


def _is_public(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip.split("%")[0]).is_global
    except ValueError:
        return False


def normalize_url(raw: str) -> str:
    url = raw.strip()
    if not url or len(url) > 2048:
        raise SiteError("that doesn't look like a web address")
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise SiteError("only http and https addresses are supported")
    if not parts.hostname:
        raise SiteError("that doesn't look like a web address")
    if parts.username or parts.password:
        raise SiteError("addresses with a login in them aren't supported")
    try:
        port = parts.port
    except ValueError:
        raise SiteError("that address has an invalid port") from None
    if port not in ALLOWED_PORTS:
        raise SiteError("only the standard web ports are supported")
    return url


async def _check_public(url: str, resolve: Resolver, is_public: Callable[[str], bool] = _is_public) -> None:
    host = urlsplit(url).hostname or ""
    addresses = [host] if _looks_like_ip(host) else await resolve(host)
    if not addresses or not all(is_public(a) for a in addresses):
        raise SiteError("that address isn't a public website")


def _looks_like_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "head"}
    BLOCK = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr", "section", "article", "header", "footer"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.title = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if tag in self.SKIP and tag != "head":
            self._skip += 1
        if tag in self.BLOCK:
            self.parts.append(" ")
        if tag == "meta" and dict(attrs).get("name", "").lower() == "description":
            self.parts.append(" " + (dict(attrs).get("content") or "") + " ")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in self.SKIP and tag != "head" and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def extract_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = " ".join((parser.title + " " + "".join(parser.parts)).split())
    return text[:MAX_TEXT_CHARS]


async def fetch_site_text(
    raw_url: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
    resolve: Resolver = system_resolver,
) -> Tuple[str, str]:
    """Return (final_url, readable_text) or raise SiteError."""
    url = normalize_url(raw_url)
    own_client = client is None
    http = client or httpx.AsyncClient(timeout=httpx.Timeout(8.0), headers={"User-Agent": USER_AGENT})
    try:
        for _ in range(MAX_REDIRECTS + 1):
            await _check_public(url, resolve)
            try:
                async with http.stream("GET", url, follow_redirects=False) as response:
                    server = response.extensions.get("network_stream")
                    peer = server.get_extra_info("server_addr") if server else None
                    if peer and not _is_public(str(peer[0])):
                        raise SiteError("that address isn't a public website")
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise SiteError("the site redirected without saying where")
                        url = normalize_url(urljoin(url, location))
                        continue
                    if response.status_code >= 400:
                        raise SiteError(f"the site answered with an error ({response.status_code})")
                    kind = response.headers.get("content-type", "").lower()
                    if "html" not in kind and "text/plain" not in kind:
                        raise SiteError("that address isn't a web page")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            break
                    html = bytes(body[:MAX_BYTES]).decode(response.encoding or "utf-8", errors="replace")
                    text = extract_text(html)
                    if not text:
                        raise SiteError("the page has no readable text")
                    return url, text
            except httpx.TimeoutException:
                raise SiteError("the site took too long to answer") from None
            except httpx.HTTPError:
                raise SiteError("the site couldn't be reached") from None
        raise SiteError("the site redirected too many times")
    finally:
        if own_client:
            await http.aclose()
