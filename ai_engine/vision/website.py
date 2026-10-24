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

GENERIC_FONTS = {
    "system-ui", "sans-serif", "serif", "monospace", "ui-sans-serif", "ui-serif", "ui-monospace", "cursive",
    "fantasy", "-apple-system", "blinkmacsystemfont", "segoe ui", "arial", "helvetica", "helvetica neue",
    "times new roman", "times", "courier new", "georgia", "verdana", "tahoma", "roboto", "inherit",
}
MIN_FONT_USES = 3
PALETTE_DISTANCE = 80
MIN_COLOR_SHARE = 0.04


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

        if facts.get("stillLoading"):
            out.append(_finding("Still on a loading screen", V.MEDIUM, W,
                f"After {facts.get('settleSeconds', 25):.0f} seconds the page was still showing a loading screen, so this check "
                "may only reflect the loader. Visitors on slower connections wait at least as long. Try a lighter first screen.",
                "Page performance best practice (WCAG 2.2.1 Timing Adjustable)"))
        elif float(facts.get("settleSeconds") or 0) >= 6:
            out.append(_finding("Slow to show content", V.LOW, W,
                f"The page took about {facts['settleSeconds']:.0f} seconds before it stopped changing. "
                "Show the main content sooner, or give the loading screen a way to skip.",
                "Page performance best practice"))

        missing, total = int(facts.get("imagesMissingAlt") or 0), int(facts.get("images") or 0)
        if missing:
            eg = ", ".join(facts.get("missingAltExamples") or [])
            out.append(_finding("Images without alt text", V.MEDIUM, W,
                f"{missing} of {total} images have no alt attribute, so screen readers can't describe them. "
                f"Add short descriptive alt text (or alt=\"\" for purely decorative images). Examples: {eg}",
                "WCAG 2.1 AA 1.1.1 Non-text Content"))

        if facts.get("autoplayWithSound"):
            out.append(_finding("Autoplay with sound", V.MEDIUM, W,
                f"{facts['autoplayWithSound']} audio or video element(s) start playing with sound. "
                "Remove autoplay or add visible controls and keep it muted.",
                "WCAG 2.1 AA 1.4.2 Audio Control"))
        if facts.get("autoplayMovingNoControls"):
            out.append(_finding("Moving video without controls", V.MEDIUM, W,
                f"{facts['autoplayMovingNoControls']} autoplaying video(s) have no pause control. "
                "Add controls, or a visible pause button, for anything that moves on its own.",
                "WCAG 2.1 AA 2.2.2 Pause, Stop, Hide"))
        if facts.get("legacyMotion"):
            out.append(_finding("Blinking or scrolling text", V.MEDIUM, W,
                "The page uses <marquee> or <blink>, which can't be paused. Replace them with static text or a controllable component.",
                "WCAG 2.1 AA 2.2.2 Pause, Stop, Hide"))

        animated = int(facts.get("animatedElements") or 0)
        if animated and not facts.get("reducedMotionSupport"):
            out.append(_finding("Animations ignore reduced-motion setting", V.MEDIUM if animated >= 5 else V.LOW, W,
                f"{animated} element(s) are animated, but the site's CSS never checks prefers-reduced-motion. "
                "Wrap animations in @media (prefers-reduced-motion: no-preference) or switch them off when the visitor asks for less motion.",
                "WCAG 2.1 AAA 2.3.3 Animation from Interactions (best practice)"))

        if not facts.get("title"):
            out.append(_finding("Missing page title", V.LOW, W, "The page has no <title>, which is what browser tabs, search results and screen readers announce.", "WCAG 2.1 AA 2.4.2 Page Titled"))
        if int(facts.get("h1") or 0) == 0:
            out.append(_finding("No main heading", V.LOW, W, "The page has no <h1>. A single clear main heading helps visitors and screen readers orient themselves.", "WCAG 2.1 AA 1.3.1 Info and Relationships"))
        if not facts.get("lang"):
            out.append(_finding("Missing page language", V.LOW, W, "The <html> element has no lang attribute, so screen readers may pronounce the text wrongly.", "WCAG 2.1 AA 3.1.1 Language of Page"))
        if not facts.get("viewportMeta"):
            out.append(_finding("Not set up for mobile", V.LOW, W, "There is no viewport meta tag, so phones may show the desktop layout shrunk down.", "Responsive design best practice"))

        style = policy.visual_style
        allowed = {f.strip().lower() for f in style.fonts if f.strip()}
        if allowed:
            used = sorted(((n, f) for f, n in (facts.get("fonts") or {}).items()), reverse=True)
            stray = [(f, n) for n, f in used if n >= MIN_FONT_USES and f.lower() not in allowed and f.lower() not in GENERIC_FONTS]
            if stray:
                names = ", ".join(f"{f} ({n} elements)" for f, n in stray[:4])
                out.append(_finding("Fonts outside the brand", V.MEDIUM, W,
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
                out.append(_finding("Colours outside the brand palette", V.LOW, W,
                    f"Prominent colours that aren't in the brand palette: {names}. Brand colours: {', '.join(style.colors)}.",
                    "Brand Identity Guidelines: Colour"))
        return out
