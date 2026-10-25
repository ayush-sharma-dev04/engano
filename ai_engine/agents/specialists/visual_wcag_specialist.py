"""Visual and WCAG Specialist Agent.

Evaluates accessibility, contrast ratios (4.5:1 normal, 3:1 large), alt-text presence,
and brand logo margins across images and visual metadata.
Strictly avoids hallucinating or faking visual measurements when data is unavailable.
"""

from typing import List, Optional
from ai_engine.agents.specialists.base import BaseSpecialist
from ai_engine.rules.accessibility import evaluate_accessibility
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)
from ai_engine.schemas.payload import DraftPayload, VisualMetadata


class VisualWCAGSpecialist(BaseSpecialist):
    """Specialist responsible for WCAG AA compliance and visual brand guidelines."""

    @property
    def name(self) -> str:
        return "VisualWCAGSpecialist"

    def evaluate(self, payload: DraftPayload, policy: BrandPolicy) -> List[Finding]:
        # Only runs if images or visual metadata exist
        if not payload.has_images_or_visuals:
            return []

        findings: List[Finding] = []
        vm = payload.visual_metadata

        # If visual_metadata is provided, evaluate via evaluate_accessibility
        if vm is not None:
            findings.extend(evaluate_accessibility(vm, policy))

        # Check individual images in payload.images
        acc_rules = policy.accessibility_rules
        for idx, img in enumerate(payload.images):
            # Check alt text for individual image
            if acc_rules.require_alt_text and not img.alt_text:
                # Avoid duplicate if already flagged via visual_metadata
                if not any(f.finding_id == "a11y_missing_alt_text" for f in findings):
                    img_label = img.url or f"Image #{idx + 1}"
                    findings.append(
                        Finding(
                            finding_id=f"a11y_img_missing_alt_{idx}",
                            category=FindingCategory.VISUAL_WCAG,
                            severity=FindingSeverity.MEDIUM,
                            highlighted_text=img_label,
                            text_span=TextSpan(start=0, end=0),
                            explanation=(
                                f"Attached visual media '{img_label}' lacks descriptive alt text."
                                + (
                                    f" Suggested alt text: “{img.metadata['suggested_alt']}”."
                                    if (img.metadata or {}).get("suggested_alt")
                                    else ""
                                )
                            ),
                            evidence_status=EvidenceStatus.VERIFIED,
                            cited_source="WCAG 2.1 AA 1.1.1 Non-text Content",
                            suggested_fix=(
                                f"Add alt text, for example: “{img.metadata['suggested_alt']}”"
                                if (img.metadata or {}).get("suggested_alt")
                                else "Add descriptive alternative text for accessibility."
                            ),
                            human_review_required=True,
                            image_index=idx + 1,
                            suggested_alt=(img.metadata or {}).get("suggested_alt"),
                        )
                    )

            # Check individual image contrast if provided
            if img.contrast_ratio is not None:
                threshold = (
                    acc_rules.min_large_contrast
                    if img.is_large_text
                    else acc_rules.min_normal_contrast
                )
                if img.contrast_ratio < threshold:
                    findings.append(
                        Finding(
                            finding_id=f"a11y_img_contrast_{idx}",
                            category=FindingCategory.VISUAL_WCAG,
                            severity=FindingSeverity.HIGH,
                            highlighted_text=f"Contrast ratio {img.contrast_ratio:.2f}:1",
                            text_span=TextSpan(start=0, end=0),
                            explanation=(
                                f"Image text contrast ratio of {img.contrast_ratio:.2f}:1 "
                                f"fails WCAG AA minimum ({threshold:.1f}:1 required)."
                            ),
                            evidence_status=EvidenceStatus.VERIFIED,
                            cited_source="WCAG 2.1 AA 1.4.3 Contrast",
                            suggested_fix=f"Increase text contrast to at least {threshold:.1f}:1.",
                            human_review_required=True,
                            image_index=idx + 1,
                        )
                    )

            # Check individual logo clear space
            if img.logo_clear_space_met is False:
                findings.append(
                    Finding(
                        finding_id=f"a11y_img_logo_margin_{idx}",
                        category=FindingCategory.VISUAL_WCAG,
                        severity=FindingSeverity.LOW,
                        highlighted_text="Brand Logo Margin",
                        text_span=TextSpan(start=0, end=0),
                        explanation="Logo clear-space margin requirement violated in attached image.",
                        evidence_status=EvidenceStatus.VERIFIED,
                        cited_source="Brand Identity Guidelines: Logo Clear Space",
                        suggested_fix="Ensure minimum clear space is preserved around the logo.",
                        human_review_required=False,
                        image_index=idx + 1,
                    )
                )

        return findings
