"""Open a creator's website in a real (headless) browser and collect what a reviewer would see.

Everything the browser does goes through SafeProxy, which only connects to public addresses,
so a hostile page cannot use this server to reach internal services. Each render gets a fresh,
throw-away browser context, downloads and service workers are off, and the whole thing has a
hard time limit.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Optional

import httpx

from .safe_proxy import SafeProxy
from .website import Resolver, SiteError, _check_public, _is_public, normalize_url, system_resolver

log = logging.getLogger("engano.render")

VIEWPORT = {"width": 1280, "height": 800}
MAX_SCREENSHOTS = 3
PAGE_TIMEOUT_MS = 20_000
TOTAL_TIMEOUT_S = 70
MAX_TEXT_CHARS = 20_000
SETTLE_MAX_SECONDS = 25      # how long to wait for a page to finish loading and stop moving
SETTLE_POLL_MS = 600
LOADING_WORDS = re.compile(r"\b(loading|please wait|initiali[sz]ing|starting up|booting)\b", re.I)
_SLOTS = asyncio.Semaphore(2)  # Chromium is heavy: at most two renders at once

# Runs inside the page. Read-only: it measures, it never changes the page.
FACTS_JS = """
() => {
  const q = (s) => Array.from(document.querySelectorAll(s));
  const all = q('body *').slice(0, 3000);
  const imgs = q('img');
  const noAlt = imgs.filter((i) => !i.hasAttribute('alt') && i.getAttribute('role') !== 'presentation' && i.width * i.height > 100);
  const autoplay = q('video[autoplay],audio[autoplay]');
  const loudAutoplay = autoplay.filter((m) => !(m.muted || m.hasAttribute('muted')));
  const movingAutoplay = autoplay.filter((m) => m.tagName === 'VIDEO' && !m.hasAttribute('controls'));
  let animated = 0, transitions = 0;
  for (const e of all) {
    const cs = getComputedStyle(e);
    if (cs.animationName && cs.animationName !== 'none' && parseFloat(cs.animationDuration) > 0) animated++;
    if (parseFloat(cs.transitionDuration) > 0) transitions++;
  }
  let reducedMotion = false;
  const scan = (rules) => { for (const r of rules) {
      if (r.media && /prefers-reduced-motion/.test(r.media.mediaText)) reducedMotion = true;
      if (r.cssRules) { try { scan(r.cssRules) } catch (e) {} } } };
  for (const sheet of document.styleSheets) { try { scan(sheet.cssRules) } catch (e) {} }
  const fonts = {};
  for (const e of all) {
    if (!Array.from(e.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
    const f = getComputedStyle(e).fontFamily.split(',')[0].replace(/["']/g, '').trim();
    if (f) fonts[f] = (fonts[f] || 0) + 1;
  }
  return {
    title: document.title || '',
    lang: document.documentElement.lang || '',
    description: (document.querySelector('meta[name=description]') || {}).content || '',
    h1: q('h1').length,
    images: imgs.length,
    imagesMissingAlt: noAlt.length,
    missingAltExamples: noAlt.slice(0, 3).map((i) => String(i.currentSrc || i.src).slice(0, 120)),
    autoplayWithSound: loudAutoplay.length,
    autoplayMovingNoControls: movingAutoplay.length,
    animatedElements: animated,
    transitionElements: transitions,
    reducedMotionSupport: reducedMotion,
    legacyMotion: q('marquee,blink').length,
    fonts,
    viewportMeta: !!document.querySelector('meta[name=viewport]'),
    pageHeight: document.documentElement.scrollHeight,
  };
}
"""


@dataclass
class RenderedSite:
    final_url: str
    title: str
    text: str
    screenshots: List[bytes] = field(default_factory=list)
    facts: Dict[str, Any] = field(default_factory=dict)


def remote_renderer_url() -> str:
    """Where the Docker renderer lives (ENGANO_RENDERER_URL), or '' to render in-process."""
    return os.getenv("ENGANO_RENDERER_URL", "").strip().rstrip("/")


def renderer_available() -> bool:
    if remote_renderer_url():
        return True
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


async def _render_remote(base_url: str, url: str, client: Optional[httpx.AsyncClient] = None) -> RenderedSite:
    """Ask the Docker renderer to open the page. Its answer is treated as untrusted data."""
    headers = {"X-Renderer-Token": os.getenv("ENGANO_RENDERER_TOKEN", "")} if os.getenv("ENGANO_RENDERER_TOKEN") else {}
    http = client or httpx.AsyncClient(timeout=httpx.Timeout(TOTAL_TIMEOUT_S + 15))
    try:
        resp = await http.post(f"{base_url}/render", json={"url": url}, headers=headers)
    except httpx.ConnectError:
        raise SiteError("the website checker isn't running (start it with `make renderer`)") from None
    except httpx.TimeoutException:
        raise SiteError("the site took too long to load") from None
    except httpx.HTTPError:
        raise SiteError("the website checker couldn't be reached") from None
    finally:
        if client is None:
            await http.aclose()
    if resp.status_code == 422:
        try:
            detail = str(resp.json().get("detail") or "")
        except ValueError:
            detail = ""
        raise SiteError(detail[:200] or "the site couldn't be opened")
    if resp.status_code != 200:
        raise SiteError("the website checker failed")
    try:
        data = resp.json()
        shots = [base64.b64decode(b, validate=True) for b in list(data["screenshots"])[:MAX_SCREENSHOTS]]
        return RenderedSite(
            final_url=str(data["final_url"])[:2048],
            title=str(data.get("title") or "")[:300],
            text=str(data.get("text") or "")[:MAX_TEXT_CHARS],
            screenshots=shots,
            facts=dict(data.get("facts") or {}),
        )
    except (KeyError, TypeError, ValueError):
        raise SiteError("the website checker gave an unreadable answer") from None


async def render_site(
    raw_url: str,
    *,
    resolve: Resolver = system_resolver,
    is_public: Callable[[str], bool] = _is_public,
    allowed_ports: Optional[FrozenSet[int]] = None,
) -> RenderedSite:
    """Render a public web page. Raises SiteError with a message that is safe to show."""
    url = normalize_url(raw_url)
    await _check_public(url, resolve, is_public)  # fail fast with a friendly message; the proxy enforces it for real
    remote = remote_renderer_url()
    if remote:
        return await _render_remote(remote, url)
    if not renderer_available():
        raise SiteError("website checks aren't set up on this server (run `make renderer`)")
    async with _SLOTS:
        try:
            return await asyncio.wait_for(_render(url, resolve, is_public, allowed_ports), TOTAL_TIMEOUT_S)
        except asyncio.TimeoutError:
            raise SiteError("the site took too long to load") from None


async def _render(url: str, resolve: Resolver, is_public: Callable[[str], bool], allowed_ports) -> RenderedSite:
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import async_playwright

    extra = {"allowed_ports": allowed_ports} if allowed_ports else {}
    proxy = SafeProxy(resolve=resolve, is_public=is_public, **extra)
    port = await proxy.start()
    try:
        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch(
                    headless=True,
                    proxy={"server": f"http://127.0.0.1:{port}"},
                    args=[
                        "--proxy-bypass-list=<-loopback>",
                        "--disable-extensions",
                        "--mute-audio",
                        # Inside the Docker container the container itself is the sandbox.
                        *(["--no-sandbox"] if os.getenv("ENGANO_RENDERER_NO_SANDBOX") == "1" else []),
                    ],
                )
            except PlaywrightError:
                raise SiteError("the browser for website checks isn't installed on this server") from None
            try:
                context = await browser.new_context(
                    viewport=VIEWPORT,
                    accept_downloads=False,
                    service_workers="block",
                    java_script_enabled=True,
                    locale="en-US",
                )
                page = await context.new_page()
                page.set_default_timeout(PAGE_TIMEOUT_MS)

                async def only_web(route):
                    scheme = route.request.url.split(":", 1)[0].lower()
                    if scheme in ("http", "https", "data", "blob", "about"):
                        await route.continue_()
                    else:
                        await route.abort()

                await context.route("**/*", only_web)
                try:
                    response = await page.goto(url, wait_until="load", timeout=PAGE_TIMEOUT_MS)
                except PlaywrightError as exc:
                    if proxy.refused:
                        raise SiteError("that address isn't a public website") from None
                    raise SiteError(_friendly(exc)) from None
                if response is None or response.status >= 400:
                    raise SiteError(f"the site answered with an error ({response.status if response else 'no response'})")
                waited, settled, still_loading = await _settle(page)

                facts = await page.evaluate(FACTS_JS)
                facts.update(settleSeconds=round(waited, 1), settled=settled, stillLoading=still_loading)
                try:
                    text = (await page.inner_text("body"))[:MAX_TEXT_CHARS]
                except PlaywrightError:
                    text = ""
                shots: List[bytes] = []
                height = int(facts.get("pageHeight") or VIEWPORT["height"])
                for i in range(MAX_SCREENSHOTS):
                    offset = i * VIEWPORT["height"]
                    if i and offset >= height:
                        break
                    await page.evaluate(f"window.scrollTo(0, {offset})")
                    await page.wait_for_timeout(500)
                    shots.append(await page.screenshot(type="png"))
                if not (text.strip() or shots):
                    raise SiteError("the page has nothing to show")
                return RenderedSite(final_url=page.url, title=str(facts.get("title") or ""), text=text, screenshots=shots, facts=facts)
            finally:
                await browser.close()
    finally:
        await proxy.stop()


async def _settle(page) -> tuple:
    """Wait for the page to finish loading and stop changing before it is photographed.

    Many sites (single-page apps especially) show a loading screen long after the browser's
    "load" event. We wait for the network to go quiet, then for two identical frames in a row
    with no "loading" wording on screen, but never longer than SETTLE_MAX_SECONDS.
    Returns (seconds waited, settled, still showing a loading screen).
    """
    from playwright.async_api import Error as PlaywrightError

    loop = asyncio.get_running_loop()
    start = loop.time()
    try:
        await page.wait_for_load_state("networkidle", timeout=8000)
    except PlaywrightError:
        pass  # chatty pages never go idle; the frame check below still applies
    previous, same, loading = None, 0, False
    while loop.time() - start < SETTLE_MAX_SECONDS:
        try:
            frame = await page.screenshot(type="jpeg", quality=35)
            text = (await page.inner_text("body"))[:2000]
        except PlaywrightError:
            break
        loading = bool(LOADING_WORDS.search(text)) and len(text.strip()) < 600
        same = same + 1 if (frame == previous and not loading) else 0
        previous = frame
        if same >= 2:
            return loop.time() - start, True, False
        await page.wait_for_timeout(SETTLE_POLL_MS)
    return loop.time() - start, False, loading


def _friendly(exc: Exception) -> str:
    message = str(exc)
    if "ERR_NAME_NOT_RESOLVED" in message:
        return "that address doesn't exist"
    if "ERR_CERT" in message or "SSL" in message:
        return "the site's security certificate isn't valid"
    if "Timeout" in message or "ERR_TIMED_OUT" in message:
        return "the site took too long to load"
    return "the site couldn't be opened"
