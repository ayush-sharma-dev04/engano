"""Look at the images in a draft and record what was measured on each ImageItem.

Per image: decode safely, read its text (Tesseract), measure real text/background contrast,
ask the vision model what it shows and which logos appear, and check clear space around the
brand logo. The findings themselves come from ImageAnalysisSpecialist and the existing
VisualWCAGSpecialist, which read what is stored here.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from ai_engine.agents.questions import brand_names
from ai_engine.providers.base import BaseProvider
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.payload import DraftPayload, ImageItem
from ai_engine.vision import imaging, ocr

logger = logging.getLogger(__name__)

MIN_WORD_CONF = 75
MIN_WORD_LEN = 3
LARGE_TEXT_HEIGHT_RATIO = 0.04
LARGE_TEXT_MIN_PX = 40


def has_image_data(img: ImageItem) -> bool:
    return bool((img.metadata or {}).get("base64"))


def is_brand_name(name: str, policy: BrandPolicy) -> bool:
    lowered = name.strip().lower()
    return any(lowered in known or known in lowered for known in brand_names(policy) if len(known) >= 3)


STOPWORDS = {
    "a", "an", "the", "of", "and", "or", "in", "on", "at", "for", "to", "with", "is", "are", "image", "photo",
    "picture", "shows", "showing", "this", "that", "from", "our", "your", "its", "into", "over", "near",
}


def content_words(text: str) -> set:
    words = {"".join(c for c in w if c.isalnum()) for w in text.lower().split()}
    return {w for w in words if len(w) >= 4 and w not in STOPWORDS}


def alt_text_disagrees(alt: str, description: str, ocr_text: str) -> bool:
    """True when the alt text shares no meaningful word with what the image shows or says.

    The vision model's own yes/no on this was unreliable, so word overlap is the judge.
    """
    mine = content_words(alt)
    if len(mine) < 2:
        return False
    return not (mine & (content_words(description) | content_words(ocr_text)))


def find_wordmark(words, names):
    """Union box of consecutive OCR words that spell one of the brand's names, or None."""
    tokens = [(w.text.lower().strip(".,:;!?\"'()"), w) for w in words]
    for name in sorted(names, key=len, reverse=True):
        parts = name.split()
        if not parts:
            continue
        for i in range(len(tokens) - len(parts) + 1):
            if all(tokens[i + k][0] == parts[k] for k in range(len(parts))):
                boxes = [tokens[i + k][1].box for k in range(len(parts))]
                return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    return None


class ImageAnalyzer:
    def __init__(self, provider: Optional[BaseProvider] = None) -> None:
        self.provider = provider

    def enrich(self, payload: DraftPayload, policy: BrandPolicy) -> DraftPayload:
        """Return a copy of the payload whose images carry what was measured."""
        if not any(has_image_data(i) for i in payload.images):
            return payload
        images = [i.model_copy(deep=True) for i in payload.images]
        with ThreadPoolExecutor(max_workers=min(3, len(images))) as pool:
            list(pool.map(lambda pair: self._analyse(pair[1], policy, pair[0]), enumerate(images)))
        return payload.model_copy(update={"images": images})

    # ------------------------------------------------------------------ one image
    def _analyse(self, item: ImageItem, policy: BrandPolicy, index: int) -> None:
        meta: Dict[str, Any] = item.metadata
        if not meta.get("base64"):
            return
        try:
            decoded = imaging.decode_image(meta["base64"])
        except imaging.ImageError as exc:
            meta["analysis_error"] = str(exc)
            return
        img = decoded.image
        item.mime_type = item.mime_type or decoded.mime
        meta["width"], meta["height"] = img.width, img.height

        self._text_and_contrast(item, img, policy)
        self._understand(item, img, policy)

    def _text_and_contrast(self, item: ImageItem, img, policy: BrandPolicy) -> None:
        meta = item.metadata
        result = ocr.read_text(img)
        if result is None:
            meta["ocr_unavailable"] = True
            return
        meta["ocr_text"] = result.text
        wordmark = find_wordmark(result.words, [n for n in brand_names(policy) if len(n) >= 3])
        if wordmark:
            meta["wordmark_box"] = list(wordmark)
        words = [w for w in result.words if w.conf >= MIN_WORD_CONF and len([c for c in w.text if c.isalnum()]) >= MIN_WORD_LEN]
        measured = []
        for w in words:
            ratio = imaging.region_contrast(img, w.box)
            if ratio is None:
                continue
            height = w.box[3] - w.box[1]
            large = height >= max(LARGE_TEXT_MIN_PX, LARGE_TEXT_HEIGHT_RATIO * img.height)
            measured.append((ratio, large, w.text))
        if not measured:
            return
        rules = policy.accessibility_rules
        failing = [m for m in measured if m[0] < (rules.min_large_contrast if m[1] else rules.min_normal_contrast)]
        # One shaky word is noise; two or more failing words is a real problem.
        pool = failing if len(failing) >= 2 else measured
        worst = min(pool, key=lambda m: m[0])
        item.contrast_ratio = round(worst[0], 2)
        item.is_large_text = worst[1]
        meta["low_contrast_words"] = [m[2] for m in sorted(failing)[:3]] if len(failing) >= 2 else []

    def _understand(self, item: ImageItem, img, policy: BrandPolicy) -> None:
        meta = item.metadata
        if self.provider is None:
            meta["understanding_unavailable"] = True
            return
        small, small_b64 = imaging.for_model(img)
        try:
            understanding = self.provider.understand_image(small_b64, item.alt_text, small.width, small.height)
        except Exception as exc:  # reported as a finding, never silently ignored
            logger.warning("Vision model failed on an image: %s", exc)
            meta["understanding_error"] = str(exc)
            return
        if understanding is None:
            meta["understanding_unavailable"] = True
            return
        meta["description"] = understanding.description
        meta["logos"] = [lg.model_dump(exclude={"box"}) for lg in understanding.logos]
        meta["alt_text_reason"] = understanding.alt_text_reason
        if understanding.description:
            meta["suggested_alt"] = understanding.description

        alt_ok = understanding.alt_text_matches
        if item.alt_text and alt_text_disagrees(item.alt_text, understanding.description, meta.get("ocr_text", "")):
            alt_ok = False
            meta["alt_text_reason"] = "it shares no words with what the image shows or says"
        meta["alt_text_matches"] = alt_ok

        # The model often misses the brand's own logo, so text in the image spelling the brand counts too.
        # Logo boxes from the model are not trusted; clear space is measured around the wordmark OCR found.
        brand_in_logos = any(is_brand_name(lg.name, policy) for lg in understanding.logos)
        meta["brand_logo_seen"] = brand_in_logos or bool(meta.get("wordmark_box"))
        if meta.get("wordmark_box"):
            item.logo_clear_space_met = imaging.clear_space_met(img, meta["wordmark_box"])
