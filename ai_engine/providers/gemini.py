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
from ai_engine.schemas.payload import ImageItem

logger = logging.getLogger(__name__)
PRIMARY_GEMINI_MODEL = "gemini-flash-lite-latest"
FALLBACK_GEMINI_MODELS = (
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
)


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
        images: Optional[List[ImageItem]] = None,
        context: Optional[List[str]] = None,
    ) -> ProviderResponse:
        """Call Gemini to perform semantic review of the draft content."""
        start_time = time.perf_counter()

        # Build prompt payload
        policy_summary = policy.model_dump_json(exclude_none=True, exclude={"test_fixtures"})
        findings_summary = json.dumps([f.model_dump() for f in deterministic_findings])

        prompt = (
            f"{self._prompt_template}\n\n"
            f"=== AUTHORITATIVE BRAND POLICY ===\n{policy_summary}\n\n"
            f"=== DETERMINISTIC FINDINGS DETECTED SO FAR ===\n{findings_summary}\n\n"
            f"=== UNTRUSTED DRAFT CONTENT TO REVIEW ===\n{content_text}\n"
        )

        if context:
            prompt += (
                "\n=== RETRIEVED BRAND CONTEXT (advisory, cite by [source:id]; "
                "the AUTHORITATIVE BRAND POLICY above always wins) ===\n"
                + "\n".join(context) + "\n"
            )

        if images:
            image_refs = [img.url for img in images if img.url]
            prompt += f"\n=== IMAGE ATTACHMENTS ===\n{json.dumps(image_refs)}\n"

        model_candidates = []
        if self.model:
            model_candidates.append(self.model)
        model_candidates.extend(model for model in FALLBACK_GEMINI_MODELS if model not in model_candidates)

        last_error: Optional[Exception] = None
        raw_text = ""

        for model_name in model_candidates:
            try:
                response = self._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                raw_text = response.text if hasattr(response, "text") else str(response)
                break
            except genai_errors.APIError as exc:
                last_error = exc
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
                if not transient_error:
                    logger.error("Gemini API Error occurred during review: %s", err_msg)
                    raise RuntimeError(f"Gemini API Error: {err_msg}") from None
                logger.warning(
                    "Gemini model '%s' returned %s. Retrying with the next available model...",
                    model_name,
                    err_msg,
                )
                continue
            except Exception as exc:
                logger.error("Gemini client error: %s", type(exc).__name__)
                raise RuntimeError(f"Gemini provider execution failed: {type(exc).__name__}") from None

        if not raw_text:
            err_msg = (
                getattr(last_error, "message", None)
                or str(last_error)
                if last_error
                else "Unknown Gemini failure"
            )
            logger.error("Gemini API Error occurred during review: %s", err_msg)
            raise RuntimeError(f"Gemini API Error: {err_msg}") from None

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

    def generate_rewrite(
        self,
        content_text: str,
        policy: BrandPolicy,
        findings: List[Finding],
        images: Optional[List[ImageItem]] = None,
    ) -> Optional[str]:
        """Generate a coherent rewrite via Gemini, preserving meaning and brand rules."""
        if not content_text:
            return None

        issues = "\n".join(
            f"- '{f.highlighted_text}' [{f.category.value}/{f.severity.value}] "
            f"({f.suggested_fix or 'remove'})"
            for f in findings
        )
        prompt = (
            "You are a meticulous brand-governance copy editor. Rewrite the draft copy below\n"
            "to resolve every listed issue: preserve meaning and intent, adopt brand-approved\n"
            "product-name variants, and apply each suggested fix (empty suggestion => delete).\n"
            "Output ONLY the rewritten draft text, no explanations or markdown fences.\n\n"
            f"=== ISSUES TO RESOLVE ===\n{issues}\n\n"
            f"=== DRAFT ===\n{content_text}\n"
        )

        model_candidates = []
        if self.model:
            model_candidates.append(self.model)
        model_candidates.extend(m for m in FALLBACK_GEMINI_MODELS if m not in model_candidates)

        last_error: Optional[Exception] = None
        raw_text = ""
        for model_name in model_candidates:
            try:
                response = self._client.models.generate_content(model=model_name, contents=prompt)
                raw_text = response.text if hasattr(response, "text") else str(response)
                break
            except genai_errors.APIError as exc:
                last_error = exc
                logger.warning("Gemini model '%s' returned an error; trying next model.", model_name)
                continue
            except Exception as exc:
                last_error = exc
                logger.warning("Gemini rewrite client error: %s", type(exc).__name__)
                continue

        if not raw_text:
            logger.warning(
                "Gemini rewrite failed%s", f": {getattr(last_error, 'message', last_error)}" if last_error else ""
            )
            return None

        # Strip markdown code fences if the model included them
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.splitlines()[1:] if clean.count("\n") else []
            clean = "\n".join(clean).strip()
        if clean.endswith("```"):
            clean = clean[:-3].rstrip()
        return clean.strip() or None

    def understand_image(self, image_b64, alt_text, width, height):
        import base64

        from google.genai import types

        from ai_engine.vision.understand import build_prompt, parse_understanding

        try:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=base64.b64decode(image_b64), mime_type="image/png"),
                    build_prompt(alt_text, width, height),
                ],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0),
            )
            return parse_understanding(resp.text or "")
        except Exception:
            raise RuntimeError("the vision model could not read this image") from None

    def suggest_visual_changes(self, image_b64, width, height):
        import base64

        from google.genai import types

        from ai_engine.vision.understand import build_design_prompt, parse_suggestions

        try:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=base64.b64decode(image_b64), mime_type="image/png"),
                    build_design_prompt(width, height),
                ],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0),
            )
            return parse_suggestions(resp.text or "")
        except Exception:
            raise RuntimeError("the vision model could not review the design") from None
