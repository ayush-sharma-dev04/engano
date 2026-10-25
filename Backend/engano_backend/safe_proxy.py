"""A tiny forward proxy that only ever connects to public internet addresses.

The browser that renders a creator's website is pointed at this proxy, so *everything* it
does (page loads, scripts, images, redirects, WebSockets) is filtered at the connection level:
the proxy resolves each name itself, refuses unless every address is public, and connects to
the address it checked. That closes the usual holes (redirects to internal hosts, DNS
rebinding, JavaScript calling 127.0.0.1 or cloud metadata addresses).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional, Tuple
from urllib.parse import urlsplit

from .website import Resolver, _is_public, _looks_like_ip, system_resolver

log = logging.getLogger("engano.proxy")

ALLOWED_PORTS = {80, 443}
MAX_HEADER_BYTES = 16 * 1024
CONNECT_TIMEOUT = 10
IDLE_TIMEOUT = 25
MAX_BYTES_PER_CONNECTION = 25 * 1024 * 1024


class SafeProxy:
    def __init__(
        self,
        resolve: Resolver = system_resolver,
        is_public: Callable[[str], bool] = _is_public,
        allowed_ports: frozenset = frozenset(ALLOWED_PORTS),
    ) -> None:
        self._allowed_ports = allowed_ports
        self._resolve = resolve
        self._is_public = is_public
        self._server: Optional[asyncio.AbstractServer] = None
        self.port = 0
        self.refused: list[str] = []  # hosts we refused, for logging and tests

    async def start(self) -> int:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0, limit=MAX_HEADER_BYTES)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    # ------------------------------------------------------------------ one client
    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        remote_writer: Optional[asyncio.StreamWriter] = None
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), CONNECT_TIMEOUT)
            request_line, _, rest = head.partition(b"\r\n")
            method, target, version = request_line.decode("latin-1").split(" ", 2)
            tunnel = method.upper() == "CONNECT"

            if tunnel:
                host, _, port_text = target.rpartition(":")
                port = int(port_text)
                path = ""
            else:
                parts = urlsplit(target)
                if parts.scheme != "http" or not parts.hostname:
                    return await self._deny(writer, 400, "bad request")
                host, port = parts.hostname, parts.port or 80
                path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")

            if port not in self._allowed_ports:
                return await self._deny(writer, 403, "port not allowed", host)
            ip = await self._public_ip(host)
            if ip is None:
                return await self._deny(writer, 403, "not a public address", host)

            remote_reader, remote_writer = await asyncio.wait_for(asyncio.open_connection(ip, port), CONNECT_TIMEOUT)
            if tunnel:
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
            else:
                remote_writer.write(self._origin_form(method, path, version, rest))
                await remote_writer.drain()

            budget = [MAX_BYTES_PER_CONNECTION]
            await asyncio.gather(self._pipe(reader, remote_writer, budget), self._pipe(remote_reader, writer, budget))
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ValueError, OSError):
            pass
        finally:
            for w in (writer, remote_writer):
                if w is not None:
                    try:
                        w.close()
                    except Exception:
                        pass

    async def _public_ip(self, host: str) -> Optional[str]:
        try:
            addresses = [host.strip("[]")] if _looks_like_ip(host.strip("[]")) else await self._resolve(host)
        except Exception:
            return None
        if not addresses or not all(self._is_public(a) for a in addresses):
            return None
        return addresses[0]

    async def _deny(self, writer: asyncio.StreamWriter, status: int, why: str, host: str = "") -> None:
        if host:
            self.refused.append(host)
            log.info("Refused %s (%s)", host, why)
        writer.write(f"HTTP/1.1 {status} {why}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".encode())
        await writer.drain()

    @staticmethod
    def _origin_form(method: str, path: str, version: str, header_block: bytes) -> bytes:
        kept = [
            line for line in header_block.split(b"\r\n")
            if line and not line.lower().startswith((b"proxy-", b"connection:", b"keep-alive:"))
        ]
        return f"{method} {path} {version}\r\n".encode() + b"\r\n".join(kept) + b"\r\nConnection: close\r\n\r\n"

    @staticmethod
    async def _pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter, budget: list) -> None:
        try:
            while True:
                chunk = await asyncio.wait_for(src.read(65536), IDLE_TIMEOUT)
                if not chunk:
                    break
                budget[0] -= len(chunk)
                if budget[0] < 0:
                    break
                dst.write(chunk)
                await dst.drain()
        except (asyncio.TimeoutError, OSError):
            pass
        finally:
            try:
                dst.close()
            except Exception:
                pass
