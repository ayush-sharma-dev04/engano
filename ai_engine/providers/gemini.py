"""Google Gemini review provider using official google-genai SDK.

Handles credential safety, structured output generation, error handling,
and Pydantic validation without requiring live calls in offline tests.
"""

import json
import logging
import os
from pathlib import Path
import time
from typing import Any, List, Optional
from google import genai
from google.genai import errors as genai_errors
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
PRIMARY_GEMINI_MODEL = "gemini-flash-lite-latest"
FALLBACK_GEMINI_MODEL = "gemini-3.1-flash-lite"


def _load_prompt_template() -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "reviewer.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return "You are a brand governance reviewer. Return findings in structured JSON."


class GeminiProvider(BaseProvider):
    """Semantic review provider using Google Gemini."""

    provider_name: str = "gemini"

    def __init__(self, config: Optional[EngineConfig] = None, client: Optional[Any] = None) -> None:
        self.config = config or get_engine_config()
        self.model = self.config.gemini_model
        self._prompt_template = _load_prompt_template()

        if client is not None:
            self._client = client
        else:
            api_key = (
                self.config.gemini_api_key.get_secret_value()
                if self.config.gemini_api_key
                else os.environ.get("GEMINI_API_KEY", "")
            )
            if not api_key:
                raise ValueError("GEMINI_API_KEY is required to initialize GeminiProvider.")
            self._client = genai.Client(api_key=api_key)

    def review(
        self,
        content_text: str,
        policy: BrandPolicy,
        deterministic_findings: List[Finding],
    ) -> ProviderResponse:
        """Call Gemini to perform semantic review of the draft content."""
        start_time = time.perf_counter()

        # Build prompt payload
        policy_summary = policy.model_dump_json(exclude_none=True)
        findings_summary = json.dumps([f.model_dump() for f in deterministic_findings])

        prompt = (
            f"{self._prompt_template}\n\n"
            f"=== AUTHORITATIVE BRAND POLICY ===\n{policy_summary}\n\n"
            f"=== DETERMINISTIC FINDINGS DETECTED SO FAR ===\n{findings_summary}\n\n"
            f"=== UNTRUSTED DRAFT CONTENT TO REVIEW ===\n{content_text}\n"
        )

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            raw_text = response.text if hasattr(response, "text") else str(response)
        except genai_errors.APIError as exc:
            err_msg = exc.message or str(exc)
            transient_error = (
                "503" in err_msg
                or "429" in err_msg
                or "rate limit" in err_msg.lower()
                or "too many requests" in err_msg.lower()
                or "high demand" in err_msg.lower()
                or "spikes in demand" in err_msg.lower()
                or "temporarily unavailable" in err_msg.lower()
                or "UNAVAILABLE" in err_msg.upper()
                or "404" in err_msg
                or "not found" in err_msg.lower()
            )
            # Retry only for transient capacity or model-availability failures. Permanent
            # auth/configuration issues should fail closed without looping.
            if transient_error and self.model != FALLBACK_GEMINI_MODEL:
                logger.warning(
                    "Primary Gemini model '%s' returned %s. Retrying with fallback model '%s'...",
                    self.model,
                    err_msg,
                    FALLBACK_GEMINI_MODEL,
                )
                try:
                    response = self._client.models.generate_content(
                        model=FALLBACK_GEMINI_MODEL,
                        contents=prompt,
                    )
                    raw_text = response.text if hasattr(response, "text") else str(response)
                except Exception as inner_exc:
                    logger.error("Gemini fallback model also failed: %s", inner_exc)
                    raise RuntimeError(f"Gemini API Error: {err_msg}") from None
            else:
                logger.error("Gemini API Error occurred during review: %s", err_msg)
                raise RuntimeError(f"Gemini API Error: {err_msg}") from None
        except Exception as exc:
            logger.error("Gemini client error: %s", type(exc).__name__)
            raise RuntimeError(f"Gemini provider execution failed: {type(exc).__name__}") from None

        # Parse structured response
        parsed_findings: List[Finding] = []
        try:
            # Strip markdown code fencing if present
            clean_json = raw_text.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            elif clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            data = json.loads(clean_json)
            findings_list = data.get("findings", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

            for item in findings_list:
                start = item.get("start", 0)
                end = item.get("end", 0)
                # Ensure end >= start and within bounds
                start = max(0, min(start, len(content_text)))
                end = max(start, min(end, len(content_text)))
                highlight = item.get("highlighted_text", content_text[start:end])

                parsed_findings.append(
                    Finding(
                        finding_id=item.get("finding_id", f"gemini_{start}_{end}"),
                        category=FindingCategory(item.get("category", "tone_mismatch")),
                        severity=FindingSeverity(item.get("severity", "medium")),
                        highlighted_text=highlight,
                        text_span=TextSpan(start=start, end=end),
                        explanation=item.get("explanation", "Semantic policy finding"),
                        evidence_status=EvidenceStatus(item.get("evidence_status", "unsupported")),
                        suggested_fix=item.get("suggested_fix"),
                        human_review_required=item.get("human_review_required", True),
                    )
                )
        except Exception as err:
            logger.warning("Failed to parse Gemini structured JSON output: %s", err)
            # Safe recovery: return empty semantic findings rather than crashing

        latency_ms = (time.perf_counter() - start_time) * 1000
        return ProviderResponse(
            provider_name="gemini",
            findings=parsed_findings,
            raw_response=raw_text,
            latency_ms=latency_ms,
        )
