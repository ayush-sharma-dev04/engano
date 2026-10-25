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
MAX_SCREENSHOTS = 6
SCROLL_MAX_STEPS = 14        # screens scrolled through, top to bottom
LINK_LIMIT = 30              # links whose address is tested
LINK_TIMEOUT_MS = 6000
MOBILE_VIEWPORT = {"width": 390, "height": 844}
PAGE_TIMEOUT_MS = 20_000
TOTAL_TIMEOUT_S = 120
MAX_TEXT_CHARS = 20_000
SETTLE_MAX_SECONDS = 25      # how long to wait for a page to finish loading and stop moving
SETTLE_POLL_MS = 600
BLOCKED_WORDS = re.compile(
    r"(verify you are (a )?human|captcha|access denied|attention required|just a moment|checking your browser|"
    r"enable javascript|request blocked|403 forbidden|you have been blocked|unusual traffic)",
    re.I,
)
LOADING_WORDS = re.compile(r"\b(loading|please wait|initiali[sz]ing|starting up|booting)\b", re.I)
_SLOTS = asyncio.Semaphore(2)  # Chromium is heavy: at most two renders at once

# Runs inside the page. Read-only: it measures, it never changes the page.
FACTS_JS = r"""
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
  // ---- stricter measurements -------------------------------------------------------------
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    const cs = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && parseFloat(cs.opacity) > 0.05;
  };
  const parse = (c) => {
    const m = /^rgba?\(([^)]+)\)$/.exec((c || '').trim());
    if (!m) return null;
    const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number);
    return p.length >= 3 && p.every((n) => !isNaN(n)) ? { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 } : null;
  };
  const mix = (top, under) => ({
    r: top.r * top.a + under.r * (1 - top.a), g: top.g * top.a + under.g * (1 - top.a), b: top.b * top.a + under.b * (1 - top.a), a: 1,
  });
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const backdrop = (el) => {            // null when the real backdrop is an image or gradient (cannot be measured)
    const layers = [];
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null;
      const c = parse(cs.backgroundColor);
      if (c && c.a > 0) { layers.push(c); if (c.a >= 0.99) break; }
    }
    return layers.reverse().reduce((under, layer) => mix(layer, under), { r: 255, g: 255, b: 255, a: 1 });
  };
  let contrastChecked = 0, tinyText = 0;
  const contrastBad = [];
  for (const e of all) {
    if (!Array.from(e.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
    if (!visible(e)) continue;
    const cs = getComputedStyle(e);
    const size = parseFloat(cs.fontSize);
    if (size < 12) tinyText++;
    const fg0 = parse(cs.color), bg = backdrop(e);
    if (!fg0 || !bg) continue;
    const fg = mix(fg0, bg);
    const [hi, lo] = [lum(fg), lum(bg)].sort((x, y) => y - x);
    const ratio = (hi + 0.05) / (lo + 0.05);
    const large = size >= 24 || (size >= 18.66 && parseInt(cs.fontWeight, 10) >= 700);
    contrastChecked++;
    if (ratio < (large ? 3 : 4.5)) {
      const hex = (c) => '#' + [c.r, c.g, c.b].map((v) => Math.round(v).toString(16).padStart(2, '0')).join('').toUpperCase();
      contrastBad.push({ text: e.textContent.trim().replace(/\s+/g, ' ').slice(0, 40), ratio: Math.round(ratio * 100) / 100, fg: hex(fg), bg: hex(bg) });
    }
  }
  contrastBad.sort((x, y) => x.ratio - y.ratio);
  const named = (e) => (e.innerText || e.textContent || '').trim() || e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') ||
    e.getAttribute('title') || (e.querySelector('img[alt]:not([alt=""])') ? 'x' : '') || (e.value && e.type !== 'password' ? e.value : '');
  const fieldLabelled = (i) => i.getAttribute('aria-label') || i.getAttribute('aria-labelledby') || i.getAttribute('title') ||
    (i.id && document.querySelector('label[for="' + CSS.escape(i.id) + '"]')) || i.closest('label');
  const fields = q('input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]):not([type=image]),select,textarea').filter(visible);
  const buttons = q('button,[role=button],input[type=submit],input[type=button]').filter(visible);
  const links = q('a[href]').filter(visible);
  const vague = /^(click here|here|read more|more|learn more|link|this|details|continue)$/i;
  const levels = q('h1,h2,h3,h4,h5,h6').map((h) => +h.tagName[1]);
  let skips = 0; for (let k = 1; k < levels.length; k++) if (levels[k] - levels[k - 1] > 1) skips++;
  const vp = (document.querySelector('meta[name=viewport]') || {}).content || '';
  const maxScale = /maximum-scale\s*=\s*([\d.]+)/i.exec(vp);
  const small = buttons.filter((b) => { const r = b.getBoundingClientRect(); return r.width < 24 || r.height < 24; });
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
    contrastChecked,
    contrastFails: contrastBad.length,
    contrastExamples: contrastBad.slice(0, 4),
    unlabelledFields: fields.filter((i) => !fieldLabelled(i)).length,
    unnamedButtons: buttons.filter((b) => !named(b)).length,
    unnamedLinks: links.filter((l) => !named(l)).length,
    vagueLinks: links.filter((l) => vague.test((l.innerText || '').trim())).length,
    headingSkips: skips,
    tinyText,
    insecure: location.protocol !== 'https:',
    zoomBlocked: /user-scalable\s*=\s*(no|0)/i.test(vp) || (maxScale ? parseFloat(maxScale[1]) < 2 : false),
    iframesNoTitle: q('iframe').filter((f) => !f.getAttribute('title')).length,
    smallTargets: small.length,
    hasMain: !!document.querySelector('main,[role=main]'),
    brokenImages: imgs.filter((i) => i.complete && i.naturalWidth === 0 && (i.currentSrc || i.src)).length,
    brokenImageExamples: imgs.filter((i) => i.complete && i.naturalWidth === 0 && (i.currentSrc || i.src)).slice(0, 3).map((i) => String(i.currentSrc || i.src).slice(0, 120)),
    outline: q('h1,h2,h3').filter(visible).slice(0, 25).map((h) => h.tagName + ' ' + (h.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 80)),
    navLinks: q('nav a[href]').filter(visible).slice(0, 14).map((a) => (a.innerText || a.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 40)).filter(Boolean),
    ctas: buttons.slice(0, 12).map((b) => (b.innerText || b.value || b.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 40)).filter(Boolean),
    forms: q('form').length,
    passwordFields: q('input[type=password]').filter(visible).length,
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
        shots = [base64.b64decode(b, validate=True) for b in list(data["screenshots"])[: MAX_SCREENSHOTS + 1]]
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

                problems: Dict[str, List[str]] = {"console": [], "pageErrors": [], "failedRequests": [], "badResponses": []}
                page.on("console", lambda m: problems["console"].append(m.text[:160]) if m.type == "error" else None)
                page.on("pageerror", lambda e: problems["pageErrors"].append(str(e)[:160]))
                page.on("requestfailed", lambda r: problems["failedRequests"].append(r.url[:120]) if r.url.startswith("http") else None)
                page.on(
                    "response",
                    lambda r: problems["badResponses"].append(f"{r.status} {r.url[:120]}")
                    if r.status >= 400 and r.request.resource_type != "document"
                    else None,
                )

                try:
                    response = await page.goto(url, wait_until="load", timeout=PAGE_TIMEOUT_MS)
                except PlaywrightError as exc:
                    if proxy.refused:
                        raise SiteError("that address isn't a public website") from None
                    raise SiteError(_friendly(exc)) from None
                if response is None:
                    raise SiteError("the site did not answer")
                status = response.status
                waited, settled, still_loading = await _settle(page)

                # Walk the whole page top to bottom (this also wakes lazy-loaded content), then back up.
                shots, scroll = await _scroll_through(page)
                facts = await page.evaluate(FACTS_JS)
                facts.update(scroll, settleSeconds=round(waited, 1), settled=settled, stillLoading=still_loading, httpStatus=status)
                try:
                    text = (await page.inner_text("body"))[:MAX_TEXT_CHARS]
                except PlaywrightError:
                    text = ""
                short = text.strip()[:1500]
                facts["blocked"] = (BLOCKED_WORDS.search(short).group(0) if len(short) < 1500 and BLOCKED_WORDS.search(short) else "")
                facts["nearlyEmpty"] = len(text.strip()) < 40
                facts["loginWall"] = bool(facts.get("passwordFields")) and len(text.strip()) < 1200
                facts.update(
                    consoleErrors=len(problems["console"]),
                    consoleExamples=problems["console"][:3],
                    pageErrors=len(problems["pageErrors"]),
                    pageErrorExamples=problems["pageErrors"][:3],
                    failedRequests=len(problems["failedRequests"]),
                    badResponses=len(problems["badResponses"]),
                    badResponseExamples=problems["badResponses"][:4],
                )

                final_url = page.url
                facts.update(await _check_links(pw, port, page, final_url))
                mobile_shot, mobile = await _mobile_check(browser, final_url, only_web)
                facts.update(mobile)
                if mobile_shot:
                    shots.append(mobile_shot)
                    facts["mobileScreenshotIndex"] = len(shots) - 1
                if not (text.strip() or shots):
                    raise SiteError("the page has nothing to show")
                return RenderedSite(final_url=final_url, title=str(facts.get("title") or ""), text=text, screenshots=shots, facts=facts)
            finally:
                await browser.close()
    finally:
        await proxy.stop()


async def _scroll_through(page) -> tuple:
    """Scroll down one screen at a time to the bottom, photographing along the way, then back to the top.

    Returns (screenshots, facts). A page that never reaches its bottom, or does not return to the top, is reported.
    """
    from playwright.async_api import Error as PlaywrightError

    height = VIEWPORT["height"]
    shots: List[bytes] = []
    last: Optional[bytes] = None
    y, steps, total = 0, 0, height
    try:
        total = int(await page.evaluate("document.documentElement.scrollHeight"))
        while steps < SCROLL_MAX_STEPS:
            await page.evaluate(f"window.scrollTo(0, {y})")
            await page.wait_for_timeout(450)
            last = await page.screenshot(type="png")
            if len(shots) < MAX_SCREENSHOTS:
                shots.append(last)
            steps += 1
            total = int(await page.evaluate("document.documentElement.scrollHeight"))  # lazy content makes it longer
            if y + height >= total:
                break
            y += height
        if len(shots) == MAX_SCREENSHOTS and last is not None and steps > MAX_SCREENSHOTS:
            shots[-1] = last  # always include the bottom of the page
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(300)
        back_at_top = int(await page.evaluate("window.scrollY")) == 0
    except PlaywrightError:
        back_at_top = False
    return shots, {
        "scrolledScreens": steps,
        "pageHeightFinal": total,
        "reachedBottom": y + height >= total,
        "backAtTop": back_at_top,
    }


async def _check_links(pw, proxy_port: int, page, base_url: str) -> Dict[str, Any]:
    """Ask each distinct link on the page whether it works. Requests go through the same public-only proxy."""
    from playwright.async_api import Error as PlaywrightError

    try:
        hrefs = await page.evaluate(
            "Array.from(document.querySelectorAll('a[href]')).map((a) => a.href).filter((h) => /^https?:/.test(h)).map((h) => h.split('#')[0])"
        )
    except PlaywrightError:
        return {"linksChecked": 0, "brokenLinkCount": 0, "brokenLinks": []}
    host = re.sub(r"^https?://([^/]+).*$", r"\1", base_url)
    unique = list(dict.fromkeys(h for h in hrefs if h and h != base_url))
    unique.sort(key=lambda h: host not in h)  # the site's own links first
    unique = unique[:LINK_LIMIT]
    broken: List[str] = []
    try:
        api = await pw.request.new_context(proxy={"server": f"http://127.0.0.1:{proxy_port}"})
    except PlaywrightError:
        return {"linksChecked": 0, "brokenLinkCount": 0, "brokenLinks": []}
    gate = asyncio.Semaphore(6)

    async def probe(link: str) -> None:
        async with gate:
            try:
                reply = await api.fetch(link, method="HEAD", timeout=LINK_TIMEOUT_MS, max_redirects=5, fail_on_status_code=False)
                if reply.status in (405, 501):
                    reply = await api.get(link, timeout=LINK_TIMEOUT_MS, max_redirects=5, fail_on_status_code=False)
                status = reply.status
            except Exception:
                status = 0
            # 401/403/429 mean "not for robots", not "broken".
            if status == 0 or status in (404, 410) or status >= 500:
                broken.append(f"{status or 'no answer'} {link[:110]}")

    try:
        await asyncio.wait_for(asyncio.gather(*(probe(u) for u in unique)), 25)
    except asyncio.TimeoutError:
        pass
    finally:
        await api.dispose()
    return {"linksChecked": len(unique), "brokenLinkCount": len(broken), "brokenLinks": sorted(broken)[:6]}


async def _mobile_check(browser, url: str, route_filter) -> tuple:
    """Open the page the way a phone does and see whether it fits the screen."""
    from playwright.async_api import Error as PlaywrightError

    try:
        context = await browser.new_context(
            viewport=MOBILE_VIEWPORT, is_mobile=True, has_touch=True, accept_downloads=False, service_workers="block", locale="en-US"
        )
        try:
            await context.route("**/*", route_filter)
            page = await context.new_page()
            page.set_default_timeout(15_000)
            await page.goto(url, wait_until="load", timeout=15_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=4000)
            except PlaywrightError:
                pass
            await page.wait_for_timeout(800)
            overflow = int(
                await page.evaluate("Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0) - window.innerWidth")
            )
            return await page.screenshot(type="png"), {"mobileChecked": True, "mobileOverflowPx": max(0, overflow)}
        finally:
            await context.close()
    except PlaywrightError:
        return None, {"mobileChecked": False, "mobileOverflowPx": 0}


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
