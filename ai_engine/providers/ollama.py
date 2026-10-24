"""Local Ollama review provider for model qwen2.5vl:3b.

Executes semantic analysis against the local Ollama instance without cloud disclosure.
Handles connectivity failures, timeouts, and structured JSON parsing.
"""

import json
import logging
from pathlib import Path
import time
from typing import Any, List, Optional
import httpx
from ai_engine.config import EngineConfig, get_engine_config
from ai_engine.providers.base import BaseProvider, ProviderResponse
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)
from ai_engine.schemas.payload import ImageItem

logger = logging.getLogger(__name__)


def _load_prompt_template() -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "reviewer.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return "You are a brand governance reviewer. Return findings in structured JSON."


class OllamaProvider(BaseProvider):
    """Semantic review provider using local Ollama model."""

    provider_name: str = "ollama"

    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.config = config or get_engine_config()
        self.base_url = self.config.ollama_base_url.rstrip("/")
        self.model = self.config.ollama_model
        self.timeout = self.config.request_timeout_seconds
        self._prompt_template = _load_prompt_template()
        self._client = http_client or httpx.Client(timeout=self.timeout)

    def review(
        self,
        content_text: str,
        policy: BrandPolicy,
        deterministic_findings: List[Finding],
        images: Optional[List[ImageItem]] = None,
    ) -> ProviderResponse:
        """Execute semantic analysis via local Ollama endpoint.

        When `images` are present (URLs or base64 bytes from Discord/WhatsApp), they
        are forwarded to qwen2.5vl under the `images` key for multimodal inspection.
        """
        start_time = time.perf_counter()

        policy_summary = policy.model_dump_json(exclude_none=True)
        findings_summary = json.dumps([f.model_dump() for f in deterministic_findings])

        prompt = (
            f"{self._prompt_template}\n\n"
            f"=== AUTHORITATIVE BRAND POLICY ===\n{policy_summary}\n\n"
            f"=== DETERMINISTIC FINDINGS DETECTED SO FAR ===\n{findings_summary}\n\n"
            f"=== UNTRUSTED DRAFT CONTENT TO REVIEW ===\n{content_text}\n"
        )

        # Multimodal: forward image URLs or embedded base64 bytes for qwen2.5vl inspection
        image_refs: List[str] = []
        for img in images or []:
            if img.url:
                prompt += f"\n=== IMAGE ATTACHMENT ===\nurl: {img.url}\nalt_text: {img.alt_text or ''}\n"
                image_refs.append(img.url)
            meta = img.metadata or {}
            embedded = meta.get("base64") or meta.get("bytes")
            if embedded:
                image_refs.append(str(embedded))

        url = f"{self.base_url}/api/generate"
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "keep_alive": "1h",
            "options": {"temperature": 0.0},
        }
        if image_refs:
            payload["images"] = image_refs

        try:
            resp = self._client.post(url, json=payload)
        except httpx.ConnectError:
            raise RuntimeError(
                f"Ollama service unavailable at {self.base_url}. Local Ollama server is not reachable."
            ) from None
        except httpx.TimeoutException:
            raise RuntimeError(
                f"Ollama request timed out after {self.timeout}s for model '{self.model}'."
            ) from None
        except Exception as exc:
            raise RuntimeError(
                f"Failed to communicate with Ollama service: {type(exc).__name__}: {exc}"
            ) from None

        if resp.status_code != 200:
            raise RuntimeError(
                f"Ollama returned HTTP {resp.status_code}: {resp.text}"
            )

        try:
            body = resp.json()
            raw_text = body.get("response", "")
        except Exception as exc:
            raise RuntimeError(f"Invalid JSON envelope from Ollama: {exc}") from None

        # Parse findings from model response
        parsed_findings: List[Finding] = []
        try:
            data = json.loads(raw_text)
            items = data.get("findings", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

            for item in items:
                start = item.get("start", 0)
                end = item.get("end", 0)
                start = max(0, min(start, len(content_text)))
                end = max(start, min(end, len(content_text)))
                highlight = item.get("highlighted_text", content_text[start:end])

                cat_str = item.get("category", "tone_mismatch")
                sev_str = item.get("severity", "medium")
                ev_str = item.get("evidence_status", "unsupported")

                parsed_findings.append(
                    Finding(
                        finding_id=item.get("finding_id", f"ollama_{start}_{end}"),
                        category=FindingCategory(cat_str) if cat_str in [c.value for c in FindingCategory] else FindingCategory.TONE_MISMATCH,
                        severity=FindingSeverity(sev_str) if sev_str in [s.value for s in FindingSeverity] else FindingSeverity.MEDIUM,
                        highlighted_text=highlight,
                        text_span=TextSpan(start=start, end=end),
                        explanation=item.get("explanation", "Local semantic policy finding"),
                        evidence_status=EvidenceStatus(ev_str) if ev_str in [e.value for e in EvidenceStatus] else EvidenceStatus.UNSUPPORTED,
                        suggested_fix=item.get("suggested_fix"),
                        human_review_required=item.get("human_review_required", True),
                    )
                )
        except Exception as err:
            logger.warning("Failed to parse Ollama inner structured JSON: %s. Raw: %s", err, raw_text[:200])

        latency_ms = (time.perf_counter() - start_time) * 1000
        return ProviderResponse(
            provider_name="ollama",
            findings=parsed_findings,
            raw_response=raw_text,
            latency_ms=latency_ms,
        )

    def generate_rewrite(
        self,
        content_text: str,
        policy: BrandPolicy,
        findings: List[Finding],
        images: Optional[List[ImageItem]] = None,
    ) -> Optional[str]:
        """Generate a coherent rewrite via the local LLM, preserving meaning and brand rules."""
        if not content_text:
            return None

        issues = "\n".join(
            f"- '{f.highlighted_text}' [{f.category.value}/{f.severity.value}] "
            f"({f.suggested_fix or 'remove'})"
            for f in findings
        )

        prompt = (
            "You are a meticulous brand-governance copy editor. Rewrite the draft copy below\n"
            "to resolve every listed issue: preserve the original meaning and intent, adopt the\n"
            "brand-approved variant of product names, and address each finding using its suggested\n"
            "fix (an empty suggestion means delete that span). Output ONLY the rewritten draft\n"
            "text, with no explanations, headers, or markdown fences.\n\n"
            f"=== ISSUES TO RESOLVE ===\n{issues}\n\n"
            f"=== DRAFT ===\n{content_text}\n"
        )

        url = f"{self.base_url}/api/generate"
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "1h",
            "options": {"temperature": 0.0},
        }
        if images:
            payload["images"] = [img.url for img in images if img.url]

        try:
            resp = self._client.post(url, json=payload)
        except httpx.TimeoutException:
            raise RuntimeError(
                f"Ollama request timed out after {self.timeout}s for model '{self.model}'."
            ) from None
        except httpx.ConnectError:
            return None
        except Exception as exc:
            logger.warning("Ollama rewrite request failed: %s", exc)
            return None

        if resp.status_code != 200:
            logger.warning("Ollama rewrite returned HTTP %s", resp.status_code)
            return None

        try:
            body = resp.json()
            raw_text = body.get("response", "")
        except Exception as exc:
            logger.warning("Invalid JSON envelope from Ollama rewrite: %s", exc)
            return None

        return _clean_rewrite_output(raw_text)


def _clean_rewrite_output(raw_text: str) -> Optional[str]:
    """Strip markdown fences/whitespace and return the proposed rewrite text."""
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = text.splitlines()
        text = "\n".join(text[1:]) if len(text) > 1 else ""
        text = text.strip()
    if text.endswith("```"):
        text = text[:-3].rstrip()
    text = text.strip()
    return text or None
