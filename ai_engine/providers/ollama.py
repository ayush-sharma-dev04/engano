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

logger = logging.getLogger(__name__)


def _load_prompt_template() -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "reviewer.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return "You are a brand governance reviewer. Return findings in structured JSON."


class OllamaProvider(BaseProvider):
    """Semantic review provider using local Ollama model."""

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
    ) -> ProviderResponse:
        """Execute semantic analysis via local Ollama endpoint."""
        start_time = time.perf_counter()

        policy_summary = policy.model_dump_json(exclude_none=True)
        findings_summary = json.dumps([f.model_dump() for f in deterministic_findings])

        prompt = (
            f"{self._prompt_template}\n\n"
            f"=== AUTHORITATIVE BRAND POLICY ===\n{policy_summary}\n\n"
            f"=== DETERMINISTIC FINDINGS DETECTED SO FAR ===\n{findings_summary}\n\n"
            f"=== UNTRUSTED DRAFT CONTENT TO REVIEW ===\n{content_text}\n"
        )

        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0},
        }

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
