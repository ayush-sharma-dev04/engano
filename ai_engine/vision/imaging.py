"""Safe image decoding and pixel measurements (no AI involved)."""

from __future__ import annotations

import base64
import binascii
import io
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PIL import Image, ImageFile

MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_PIXELS = 25_000_000
MODEL_MAX_SIDE = 1024
ALLOWED_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp", "GIF": "image/gif"}

Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # guard against decompression bombs
ImageFile.LOAD_TRUNCATED_IMAGES = False


class ImageError(ValueError):
    """The image can't be used. The message is safe to show to the creator."""


@dataclass
class Decoded:
    image: Image.Image  # RGB, transparency flattened onto white
    mime: str


def decode_image(data_b64: str) -> Decoded:
    try:
        raw = base64.b64decode(data_b64, validate=True)
    except (binascii.Error, ValueError):
        raise ImageError("the image data isn't valid") from None
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ImageError(f"images must be under {MAX_IMAGE_BYTES // (1024 * 1024)} MB")
    try:
        img = Image.open(io.BytesIO(raw))
        fmt = (img.format or "").upper()
        if fmt not in ALLOWED_FORMATS:
            raise ImageError("only PNG, JPEG, WebP and GIF images are supported")
        img.load()
    except ImageError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageError("that image is too large") from None
    except Exception:
        raise ImageError("that file isn't a readable image") from None
    if img.width * img.height > MAX_PIXELS:
        raise ImageError("that image is too large")
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        base.alpha_composite(rgba)
        img = base.convert("RGB")
    else:
        img = img.convert("RGB")
    return Decoded(image=img, mime=ALLOWED_FORMATS[fmt])


def for_model(img: Image.Image) -> Tuple[Image.Image, str]:
    """A downscaled copy for the vision model, plus its base64 PNG."""
    copy = img.copy()
    copy.thumbnail((MODEL_MAX_SIDE, MODEL_MAX_SIDE))
    buf = io.BytesIO()
    copy.save(buf, format="PNG")
    return copy, base64.b64encode(buf.getvalue()).decode()


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- contrast


def _luminance(rgb: Tuple[int, int, int]) -> float:
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def region_contrast(img: Image.Image, box: Tuple[int, int, int, int]) -> Optional[float]:
    """WCAG contrast between the text and its background inside one text box.

    The background is the commonest colour in the box. Every other pixel is text or the
    soft edge around it, so the text colour is read from the strong pixels (the 90th
    percentile of contrast against the background), not from a colour average: averaging
    thin, anti-aliased text mixes it with the background and badly under-reports contrast.
    Returns None when the box is only background.
    """
    left, top, right, bottom = box
    pad = 2
    crop = img.crop((max(0, left - pad), max(0, top - pad), min(img.width, right + pad), min(img.height, bottom + pad)))
    if crop.width < 4 or crop.height < 4:
        return None
    pixels = list(crop.getdata())

    def bucket(p: Tuple[int, int, int]) -> Tuple[int, int, int]:
        return (p[0] >> 3, p[1] >> 3, p[2] >> 3)

    counts: dict = {}
    for p in pixels:
        counts[bucket(p)] = counts.get(bucket(p), 0) + 1
    bg_key = max(counts, key=counts.get)  # type: ignore[arg-type]
    bg_pixels = [p for p in pixels if bucket(p) == bg_key]
    bg = tuple(sum(p[c] for p in bg_pixels) // len(bg_pixels) for c in range(3))
    others = [p for p in pixels if bucket(p) != bg_key]
    if len(others) < max(6, int(0.02 * len(pixels))):
        return None
    cache: dict = {}
    ratios = []
    for p in others:
        if p not in cache:
            cache[p] = contrast_ratio(p, bg)  # type: ignore[arg-type]
        ratios.append(cache[p])
    ratios.sort()
    return ratios[int(0.9 * (len(ratios) - 1))]


# ---------------------------------------------------------------- logo clear space


def clear_space_met(img: Image.Image, box: List[float], margin_ratio: float = 0.25, busy_limit: float = 0.08) -> Optional[bool]:
    """Is the area around a logo quiet enough? None if the box can't be trusted.

    The margin is a fraction of the logo's shorter side. The logo is too crowded when the
    margin runs off the image edge or more than `busy_limit` of the margin ring differs
    clearly from its usual background colour.
    """
    try:
        x1, y1, x2, y2 = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    if not (0 <= x1 < x2 <= img.width and 0 <= y1 < y2 <= img.height) or (x2 - x1) < 8 or (y2 - y1) < 8:
        return None
    margin = max(4.0, margin_ratio * min(x2 - x1, y2 - y1))
    ex1, ey1, ex2, ey2 = x1 - margin, y1 - margin, x2 + margin, y2 + margin
    if ex1 < 0 or ey1 < 0 or ex2 > img.width or ey2 > img.height:
        return False
    outer = img.crop((int(ex1), int(ey1), int(ex2), int(ey2)))
    scale = min(1.0, 200 / max(outer.size))
    outer = outer.resize((max(1, int(outer.width * scale)), max(1, int(outer.height * scale))))
    ix1, iy1 = int((x1 - ex1) * scale), int((y1 - ey1) * scale)
    ix2, iy2 = int((x2 - ex1) * scale + 0.999), int((y2 - ey1) * scale + 0.999)
    pixels = outer.load()
    ring = [
        pixels[x, y]
        for y in range(outer.height)
        for x in range(outer.width)
        if not (ix1 <= x < ix2 and iy1 <= y < iy2)
    ]
    if not ring:
        return True
    mid = [sorted(p[c] for p in ring)[len(ring) // 2] for c in range(3)]
    busy = sum(1 for p in ring if sum(abs(p[c] - mid[c]) for c in range(3)) > 90)
    return busy / len(ring) <= busy_limit


def dominant_colors(img: Image.Image, n: int = 6) -> List[Tuple[Tuple[int, int, int], float]]:
    """The n most common colours (RGB) and the share of the picture each covers."""
    small = img.copy()
    small.thumbnail((200, 200))
    quant = small.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    palette = quant.getpalette() or []
    total = float(small.width * small.height)
    out = []
    for count, index in sorted(quant.getcolors() or [], reverse=True):
        out.append((tuple(palette[index * 3 : index * 3 + 3]), count / total))  # type: ignore[arg-type]
    return out
