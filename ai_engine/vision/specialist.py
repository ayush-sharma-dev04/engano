"""Turn what the image analyzer measured into findings."""

from __future__ import annotations

from typing import List

from ai_engine.agents.specialists.base import BaseSpecialist
from ai_engine.agents.specialists.claims_specialist import ClaimsSpecialist
from ai_engine.agents.specialists.legal_policy_specialist import LegalPolicySpecialist
from ai_engine.agents.specialists.rules_specialist import RulesSpecialist
from ai_engine.agents.specialists.tone_specialist import ToneSpecialist
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)
from ai_engine.schemas.payload import DraftPayload
from ai_engine.vision.analyzer import has_image_data, is_brand_name


def _image_finding(n: int, label: str, severity, category, explanation: str, source: str, **extra) -> Finding:
    return Finding(
        finding_id=f"image_{n}_{label}",
        category=category,
        severity=severity,
        highlighted_text=f"[Image {n}] {extra.pop('quote', label)}",
        text_span=TextSpan(start=0, end=0),
        explanation=f"Image {n}: {explanation}",
        evidence_status=EvidenceStatus.VERIFIED,
        cited_source=source,
        suggested_fix=None,
        human_review_required=True,
        image_index=n,
        **extra,
    )


class ImageAnalysisSpecialist(BaseSpecialist):
    @property
    def name(self) -> str:
        return "ImageAnalysisSpecialist"

    def evaluate(self, payload: DraftPayload, policy: BrandPolicy) -> List[Finding]:
        findings: List[Finding] = []
        text_rules = [RulesSpecialist(), ClaimsSpecialist(), LegalPolicySpecialist(), ToneSpecialist(provider=None)]

        for n, img in enumerate(payload.images, 1):
            if not has_image_data(img):
                continue
            meta = img.metadata

            if meta.get("analysis_error"):
                findings.append(_image_finding(
                    n, "unreadable", FindingSeverity.MEDIUM, FindingCategory.VISUAL_WCAG,
                    f"This image could not be checked ({meta['analysis_error']}).", "Image analysis",
                ))
                continue

            # 1. The words inside the image get the same rules as the draft text
            ocr_text = (meta.get("ocr_text") or "").strip()
            if len(ocr_text) >= 3:
                derived = DraftPayload(draft_id=f"{payload.draft_id}-image-{n}", brand_id=payload.brand_id, content_text=ocr_text)
                for spec in text_rules:
                    try:
                        found = spec.evaluate(derived, policy)
                    except Exception:  # one rule failing must not hide the rest
                        continue
                    for f in found:
                        adds = (f.suggested_fix or "").lower().startswith("append required disclaimer")
                        quote = "Disclaimer" if adds else f.highlighted_text
                        if adds:
                            fix = f" Add this to the image: {f.suggested_fix.split(':', 1)[1].strip()}"
                        elif f.suggested_fix and f.text_span.end > f.text_span.start:
                            fix = f" Suggested change: “{f.highlighted_text}” → “{f.suggested_fix}”."
                        else:
                            fix = ""
                        findings.append(f.model_copy(update={
                            "finding_id": f"image_{n}_{f.finding_id}",
                            "highlighted_text": f"[Image {n}] {quote}",
                            "text_span": TextSpan(start=0, end=0),
                            "explanation": f"Text in image {n}: {f.explanation}{fix}",
                            "suggested_fix": None,
                            "human_review_required": True,
                            "image_index": n,
                        }))
            elif meta.get("ocr_unavailable"):
                findings.append(_image_finding(
                    n, "no_ocr", FindingSeverity.LOW, FindingCategory.VISUAL_WCAG,
                    "The text inside this image was not read (Tesseract is not installed on the server).", "Image analysis",
                ))

            # 2. What the vision model saw
            if meta.get("understanding_error"):
                findings.append(_image_finding(
                    n, "not_understood", FindingSeverity.MEDIUM, FindingCategory.VISUAL_WCAG,
                    f"The AI could not look at this image ({meta['understanding_error']}). A person should check it.",
                    "Image analysis",
                ))
                continue
            if meta.get("understanding_unavailable") or "description" not in meta:
                continue

            suggested = meta.get("suggested_alt") or None
            if img.alt_text and meta.get("alt_text_matches") is False:
                reason = meta.get("alt_text_reason") or "the description does not match what the image shows"
                findings.append(_image_finding(
                    n, "alt_mismatch", FindingSeverity.MEDIUM, FindingCategory.VISUAL_WCAG,
                    f"The alt text doesn't seem to match the picture: {reason}.",
                    "WCAG 2.1 AA 1.1.1 Non-text Content", quote="Alt text", suggested_alt=suggested,
                ))

            logos = [lg["name"] for lg in meta.get("logos", [])]
            partners = [p.lower() for p in policy.logo_rules.approved_partners]
            for logo in logos:
                if is_brand_name(logo, policy) or any(p in logo.lower() or logo.lower() in p for p in partners):
                    continue
                findings.append(_image_finding(
                    n, f"third_party_{logo.lower().replace(' ', '_')}", FindingSeverity.MEDIUM, FindingCategory.LEGAL,
                    f"Another company's logo or name appears: “{logo}”. Confirm you have permission to use it.",
                    "Brand Identity Guidelines: Third-party marks", quote=logo,
                ))
            if policy.logo_rules.require_brand_logo and not meta.get("brand_logo_seen"):
                findings.append(_image_finding(
                    n, "no_brand_logo", FindingSeverity.MEDIUM, FindingCategory.VISUAL_WCAG,
                    f"The {policy.brand_name} logo was not found in this image.",
                    "Brand Identity Guidelines: Logo usage", quote="Brand logo",
                ))
        return findings
