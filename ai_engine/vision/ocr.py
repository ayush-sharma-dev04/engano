"""Read text out of an image with Tesseract (offline, deterministic) and keep word positions."""

from __future__ import annotations

import csv
import io
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from PIL import Image

from ai_engine.vision.imaging import png_bytes

OCR_TIMEOUT_SECONDS = 30
MAX_OCR_CHARS = 5000


@dataclass
class Word:
    text: str
    conf: float
    box: tuple  # left, top, right, bottom
    line: int


@dataclass
class OcrResult:
    text: str = ""
    words: List[Word] = field(default_factory=list)


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def read_text(img: Image.Image) -> Optional[OcrResult]:
    """None when Tesseract isn't installed or fails; an empty result when no text is found."""
    exe = shutil.which("tesseract")
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, "stdin", "stdout", "-l", "eng", "--psm", "11", "tsv"],
            input=png_bytes(img),
            capture_output=True,
            timeout=OCR_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None

    rows = csv.DictReader(io.StringIO(proc.stdout.decode("utf-8", errors="replace")), delimiter="\t", quoting=csv.QUOTE_NONE)
    words: List[Word] = []
    lines: Dict[tuple, List[str]] = {}
    for row in rows:
        text = (row.get("text") or "").strip()
        try:
            conf = float(row["conf"])
            left, top, width, height = (int(row[k]) for k in ("left", "top", "width", "height"))
        except (KeyError, TypeError, ValueError):
            continue
        if not text or conf < 0:
            continue
        key = (row.get("block_num"), row.get("par_num"), row.get("line_num"))
        lines.setdefault(key, []).append(text)
        words.append(Word(text=text, conf=conf, box=(left, top, left + width, top + height), line=len(lines)))
    text = "\n".join(" ".join(parts) for parts in lines.values())
    return OcrResult(text=text[:MAX_OCR_CHARS], words=words)
