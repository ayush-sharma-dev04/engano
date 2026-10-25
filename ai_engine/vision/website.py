"""What a rendered website needs changed, judged from measured facts (no AI opinion involved)."""

from __future__ import annotations

import base64
import colorsys
from typing import Any, Dict, List, Optional, Tuple

from ai_engine.agents.specialists.base import BaseSpecialist
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)
from ai_engine.schemas.payload import DraftPayload
from ai_engine.vision import imaging

# Only real CSS keywords are exempt. A named font (Arial, Roboto, Georgia...) that is not a brand
# font is a brand problem like any other, so a strict check does not let it through.
GENERIC_FONTS = {
    "system-ui", "sans-serif", "serif", "monospace", "ui-sans-serif", "ui-serif", "ui-monospace", "cursive",
    "fantasy", "-apple-system", "blinkmacsystemfont", "inherit",
}
MIN_FONT_USES = 2
PALETTE_DISTANCE = 60
MIN_COLOR_SHARE = 0.02
MANY_CONTRAST_FAILS = 5


def _hex_to_rgb(value: str) -> Optional[Tuple[int, int, int]]:
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        return None
    try:
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    except ValueError:
        return None


def _distance(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _is_colourful(rgb: Tuple[int, int, int]) -> bool:
    _, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    return s > 0.28 and 0.15 < v < 0.98  # ignore whites, blacks and greys: they are rarely "brand colours"


def _hex(rgb: Tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _finding(label: str, severity: FindingSeverity, category: FindingCategory, explanation: str, source: str) -> Finding:
    return Finding(
        finding_id=f"site_{label.lower().replace(' ', '_')}",
        category=category,
        severity=severity,
        highlighted_text=f"[Website] {label}",
        text_span=TextSpan(start=0, end=0),
        explanation=explanation,
        evidence_status=EvidenceStatus.VERIFIED,
        cited_source=source,
        suggested_fix=None,
        human_review_required=True,
    )


class WebsiteSpecialist(BaseSpecialist):
    @property
    def name(self) -> str:
        return "WebsiteSpecialist"

    def evaluate(self, payload: DraftPayload, policy: BrandPolicy) -> List[Finding]:
        facts: Optional[Dict[str, Any]] = payload.metadata.get("website_facts")
        if not facts:
            return []
        out: List[Finding] = []
        W, V = FindingCategory.VISUAL_WCAG, FindingSeverity

        def n(key: str) -> int:
            return int(facts.get(key) or 0)

        def add(label: str, severity: FindingSeverity, problem: str, fix: str, source: str) -> None:
            # Every finding says what is wrong and what the site's owner must do. ENGANO does not edit
            # someone else's website, so these are things to fix, not wording to paste.
            out.append(_finding(label, severity, W, f"Problem: {problem} Fix required: {fix}", source))

        # ---- ENGANO could not properly see the site: that is the site owner's problem to fix ----
        status = n("httpStatus")
        if status >= 400:
            add("Page returns an error", V.HIGH,
                f"The address answered with HTTP {status}, an error, so visitors (and ENGANO) get an error page instead of your site.",
                "Fix the page or the address so it loads normally (HTTP 200), then check it again.",
                "Site availability")
        if facts.get("blocked"):
            add("Site blocks ENGANO's checker", V.HIGH,
                f"The page showed a bot-protection or access wall (“{facts['blocked']}”), so ENGANO could not read the real site.",
                "Allow the check through your protection, or give a staging or preview address with no wall, then check again. "
                "ENGANO can't approve a site it can't see.",
                "Site accessibility to reviewers")
        if facts.get("loginWall"):
            add("Page needs a login", V.HIGH,
                "The page is a sign-in form, so ENGANO could not see the content behind it.",
                "Give a public or preview address for the page you want checked, with no login in front of it.",
                "Site accessibility to reviewers")
        if facts.get("nearlyEmpty") and not facts.get("blocked"):
            add("Page is almost empty", V.HIGH,
                "The page shows almost no text, so there is nothing real to review (it may need JavaScript that failed, or the content is missing).",
                "Make sure the page loads its content without errors, then check it again.",
                "Site availability")
        if facts.get("stillLoading"):
            add("Still on a loading screen", V.HIGH,
                f"After {facts.get('settleSeconds', 25):.0f} seconds the page was still showing a loading screen, so this check may only reflect the loader. "
                "Visitors on slower connections wait at least as long.",
                "Make the real content appear within a few seconds, or give the loading screen a way to finish.",
                "Page performance best practice (WCAG 2.2.1 Timing Adjustable)")
        elif float(facts.get("settleSeconds") or 0) >= 6:
            add("Slow to show content", V.MEDIUM,
                f"The page took about {facts['settleSeconds']:.0f} seconds before it stopped changing.",
                "Show the main content sooner, or let visitors skip the loading screen.",
                "Page performance best practice")
        if facts.get("insecure"):
            add("Not served over HTTPS", V.HIGH,
                "The page is not served over HTTPS, so what visitors send and see can be read or changed on the way, and browsers warn them.",
                "Serve the whole site over HTTPS and redirect http:// to https://.",
                "Web security best practice")
        if "reachedBottom" in facts and not facts.get("backAtTop", True):
            add("Page does not scroll back to the top", V.MEDIUM,
                "After scrolling to the bottom, ENGANO could not scroll back up: the page may trap or jump the scroll position.",
                "Check scrolling on this page (sticky or full-screen sections often cause it) and make it scroll normally both ways.",
                "WCAG 2.1 AA 2.1.1 Keyboard / usability")

        # ---- things that are broken ----
        broken_links = n("brokenLinkCount")
        if broken_links:
            eg = "; ".join(facts.get("brokenLinks") or [])
            add("Broken links", V.HIGH,
                f"{broken_links} of {n('linksChecked')} links checked do not work. Examples: {eg}",
                "Fix or remove every broken link.",
                "Content quality / WCAG 2.1 2.4.4 Link Purpose")
        if n("brokenImages"):
            eg = ", ".join(facts.get("brokenImageExamples") or [])
            add("Images that fail to load", V.HIGH,
                f"{facts['brokenImages']} image(s) are broken, so visitors see empty boxes. Examples: {eg}",
                "Fix the image addresses or upload the missing files.",
                "Content quality")
        if n("pageErrors"):
            eg = "; ".join(facts.get("pageErrorExamples") or [])
            add("Errors in the page's code", V.MEDIUM,
                f"The page's scripts threw {facts['pageErrors']} error(s) while loading: {eg}",
                "Fix the script errors; they usually mean something on the page does not work.",
                "Site reliability")
        if n("consoleErrors") >= 3 or n("badResponses") >= 3:
            eg = "; ".join((facts.get("badResponseExamples") or [])[:3])
            add("Resources fail to load", V.MEDIUM,
                f"{n('badResponses')} file(s) failed to load and the browser logged {n('consoleErrors')} error(s). Examples: {eg}",
                "Fix or remove the failing files so every part of the page loads.",
                "Site reliability")
        if facts.get("mobileChecked") and n("mobileOverflowPx") > 4:
            add("Layout breaks on phones", V.HIGH,
                f"On a phone-sized screen the page is {facts['mobileOverflowPx']} pixels wider than the screen, so visitors have to scroll sideways.",
                "Make the layout fit narrow screens (check fixed widths, wide images and tables).",
                "WCAG 2.1 AA 1.4.10 Reflow")

        # ---- accessibility, measured ----
        missing, total = n("imagesMissingAlt"), n("images")
        if missing:
            eg = ", ".join(facts.get("missingAltExamples") or [])
            add("Images without alt text", V.HIGH,
                f"{missing} of {total} images have no alt attribute, so screen readers can't describe them. Examples: {eg}",
                "Add short descriptive alt text to each (or alt=\"\" for purely decorative images).",
                "WCAG 2.1 AA 1.1.1 Non-text Content")

        fails, checked = n("contrastFails"), n("contrastChecked")
        if fails:
            eg = "; ".join(
                f"“{e.get('text', '')}” {e.get('fg', '')} on {e.get('bg', '')} = {e.get('ratio', 0)}:1" for e in (facts.get("contrastExamples") or [])[:3]
            )
            add("Low text contrast", V.HIGH if fails >= MANY_CONTRAST_FAILS else V.MEDIUM,
                f"{fails} of {checked} measured text elements are below the required contrast (4.5:1, or 3:1 for large text). Worst: {eg}.",
                "Darken the text or lighten the background until each one passes.",
                "WCAG 2.1 AA 1.4.3 Contrast (Minimum)")

        if n("autoplayWithSound"):
            add("Autoplay with sound", V.HIGH,
                f"{facts['autoplayWithSound']} audio or video element(s) start playing with sound.",
                "Remove autoplay, or keep it muted and add visible controls.",
                "WCAG 2.1 AA 1.4.2 Audio Control")
        if n("autoplayMovingNoControls"):
            add("Moving video without controls", V.HIGH,
                f"{facts['autoplayMovingNoControls']} autoplaying video(s) have no pause control.",
                "Add controls, or a visible pause button, to anything that moves on its own.",
                "WCAG 2.1 AA 2.2.2 Pause, Stop, Hide")
        if n("legacyMotion"):
            add("Blinking or scrolling text", V.HIGH,
                "The page uses <marquee> or <blink>, which can't be paused.",
                "Replace them with static text or a component visitors can control.",
                "WCAG 2.1 AA 2.2.2 Pause, Stop, Hide")

        animated = n("animatedElements")
        if animated and not facts.get("reducedMotionSupport"):
            add("Animations ignore reduced-motion setting", V.HIGH if animated >= 10 else V.MEDIUM,
                f"{animated} element(s) are animated, but the site's CSS never checks prefers-reduced-motion.",
                "Wrap animations in @media (prefers-reduced-motion: no-preference), or switch them off when the visitor asks for less motion.",
                "WCAG 2.1 AA 2.3.3 Animation from Interactions (best practice)")

        if n("unlabelledFields"):
            add("Form fields without labels", V.HIGH,
                f"{facts['unlabelledFields']} form field(s) have no label, so screen-reader users can't tell what to type.",
                "Add a <label for=...> or an aria-label to each (a placeholder is not a label).",
                "WCAG 2.1 AA 3.3.2 Labels or Instructions / 4.1.2 Name, Role, Value")
        if n("unnamedButtons") or n("unnamedLinks"):
            add("Buttons or links with no name", V.HIGH,
                f"{n('unnamedButtons')} button(s) and {n('unnamedLinks')} link(s) have no text or aria-label, so they are announced as just \"button\" or \"link\".",
                "Give each a visible label or an aria-label.",
                "WCAG 2.1 AA 4.1.2 Name, Role, Value / 2.4.4 Link Purpose")
        if n("vagueLinks"):
            add("Vague link text", V.MEDIUM,
                f"{facts['vagueLinks']} link(s) say only \"click here\", \"read more\" or similar.",
                "Rewrite each link so it makes sense on its own.",
                "WCAG 2.1 AA 2.4.4 Link Purpose (In Context)")
        if n("headingSkips"):
            add("Heading levels skipped", V.MEDIUM,
                f"Headings jump down more than one level {facts['headingSkips']} time(s) (for example h2 straight to h4).",
                "Keep heading levels in order.",
                "WCAG 2.1 AA 1.3.1 Info and Relationships")
        if n("iframesNoTitle"):
            add("Embedded frames without a title", V.MEDIUM,
                f"{facts['iframesNoTitle']} embedded frame(s) have no title attribute, so screen readers can't say what they contain.",
                "Add a title to each embedded frame.",
                "WCAG 2.1 AA 4.1.2 Name, Role, Value")
        if facts.get("zoomBlocked"):
            add("Zooming is blocked", V.HIGH,
                "The viewport setting stops visitors pinching to zoom (user-scalable=no or a low maximum-scale).",
                "Remove that setting from the viewport meta tag.",
                "WCAG 2.1 AA 1.4.4 Resize Text")
        if n("tinyText") >= 3:
            add("Text smaller than 12px", V.MEDIUM,
                f"{facts['tinyText']} text element(s) are set below 12px, which is hard to read.",
                "Use at least 12px, ideally 16px for body text.",
                "Readability best practice (WCAG 1.4.4)")
        if n("smallTargets"):
            add("Buttons too small to tap", V.MEDIUM,
                f"{facts['smallTargets']} button(s) are smaller than 24 by 24 pixels, which is hard to hit on a touch screen.",
                "Make every button at least 24 by 24 pixels.",
                "WCAG 2.2 AA 2.5.8 Target Size (Minimum)")

        if not facts.get("title"):
            add("Missing page title", V.MEDIUM, "The page has no <title>, which is what browser tabs, search results and screen readers announce.",
                "Add a clear <title> to the page.", "WCAG 2.1 AA 2.4.2 Page Titled")
        if n("h1") == 0:
            add("No main heading", V.MEDIUM, "The page has no <h1>, so visitors and screen readers have no main heading to orient by.",
                "Add one clear <h1>.", "WCAG 2.1 AA 1.3.1 Info and Relationships")
        elif n("h1") > 1:
            add("More than one main heading", V.LOW, f"The page has {facts['h1']} <h1> headings.",
                "Use one main heading and sub-headings below it.", "WCAG 2.1 AA 1.3.1 Info and Relationships")
        if not facts.get("lang"):
            add("Missing page language", V.MEDIUM, "The <html> element has no lang attribute, so screen readers may pronounce the text wrongly.",
                "Add lang=\"en\" (or the right language) to <html>.", "WCAG 2.1 AA 3.1.1 Language of Page")
        if not facts.get("viewportMeta"):
            add("Not set up for mobile", V.MEDIUM, "There is no viewport meta tag, so phones may show the desktop layout shrunk down.",
                "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.", "Responsive design best practice")
        if "hasMain" in facts and not facts.get("hasMain"):
            add("No main landmark", V.LOW, "The page has no <main> region, so keyboard and screen-reader users can't jump straight to the content.",
                "Wrap the page's main content in <main>.", "WCAG 2.1 AA 1.3.1 / 2.4.1 Bypass Blocks")
        if "description" in facts and not facts.get("description"):
            add("No page description", V.LOW, "There is no meta description, which search results and link previews use to describe the page.",
                "Add a meta description of one or two sentences.", "Content and SEO best practice")

        style = policy.visual_style
        allowed = {f.strip().lower() for f in style.fonts if f.strip()}
        if allowed:
            used = sorted(((n, f) for f, n in (facts.get("fonts") or {}).items()), reverse=True)
            stray = [(f, n) for n, f in used if n >= MIN_FONT_USES and f.lower() not in allowed and f.lower() not in GENERIC_FONTS]
            if stray:
                names = ", ".join(f"{f} ({n} elements)" for f, n in stray[:4])
                out.append(_finding("Fonts outside the brand", V.HIGH, W,
                    f"The site uses fonts that aren't brand fonts: {names}. Brand fonts: {', '.join(style.fonts)}.",
                    "Brand Identity Guidelines: Typography"))

        palette = [c for c in (_hex_to_rgb(h) for h in style.colors) if c]
        shots = [i for i in payload.images if (i.metadata or {}).get("base64")]
        if palette and shots:
            try:
                img = imaging.decode_image(shots[0].metadata["base64"]).image
                off = [
                    (rgb, share) for rgb, share in imaging.dominant_colors(img)
                    if share >= MIN_COLOR_SHARE and _is_colourful(rgb) and min(_distance(rgb, p) for p in palette) > PALETTE_DISTANCE
                ]
            except imaging.ImageError:
                off = []
            if off:
                names = ", ".join(f"{_hex(rgb)} ({share:.0%} of the first screen)" for rgb, share in off[:3])
                out.append(_finding("Colours outside the brand palette", V.MEDIUM, W,
                    f"Prominent colours that aren't in the brand palette: {names}. Brand colours: {', '.join(style.colors)}.",
                    "Brand Identity Guidelines: Colour"))
        return out
