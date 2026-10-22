"""Deterministic accessibility evaluator for Web Studio assets.

Inspects structured visual metadata against WCAG contrast and alt-text rules.
Does not fake visual/pixel inspection when metadata is absent.
"""

from typing import List, Optional
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)
from ai_engine.schemas.review import VisualMetadata


def evaluate_accessibility(
    visual_metadata: Optional[VisualMetadata],
    policy: BrandPolicy,
) -> List[Finding]:
    """Evaluate accessibility metadata against WCAG 2.1 AA thresholds."""
    findings: List[Finding] = []

    if visual_metadata is None:
        # No metadata provided; cannot evaluate visual layout deterministically
        return findings

    acc_rules = policy.accessibility_rules

    # 1. Contrast Ratio Evaluation
    if visual_metadata.contrast_ratio is not None:
        ratio = visual_metadata.contrast_ratio
        if visual_metadata.is_large_text:
            threshold = acc_rules.min_large_contrast  # Default 3.0:1
            if ratio < threshold:
                findings.append(
                    Finding(
                        finding_id="a11y_contrast_large_text",
                        category=FindingCategory.VISUAL_WCAG,
                        severity=FindingSeverity.HIGH,
                        highlighted_text=f"Contrast ratio {ratio:.2f}:1",
                        text_span=TextSpan(start=0, end=0),
                        explanation=(
                            f"Large text contrast ratio of {ratio:.2f}:1 fails WCAG AA standard "
                            f"(minimum {threshold:.1f}:1 required)."
                        ),
                        evidence_status=EvidenceStatus.VERIFIED,
                        cited_source="WCAG 2.1 AA 1.4.3 Contrast (Large Text)",
                        suggested_fix=f"Increase contrast to at least {threshold:.1f}:1",
                        human_review_required=True,
                    )
                )
        else:
            threshold = acc_rules.min_normal_contrast  # Default 4.5:1
            if ratio < threshold:
                findings.append(
                    Finding(
                        finding_id="a11y_contrast_normal_text",
                        category=FindingCategory.VISUAL_WCAG,
                        severity=FindingSeverity.HIGH,
                        highlighted_text=f"Contrast ratio {ratio:.2f}:1",
                        text_span=TextSpan(start=0, end=0),
                        explanation=(
                            f"Body text contrast ratio of {ratio:.2f}:1 fails WCAG AA standard "
                            f"(minimum {threshold:.1f}:1 required)."
                        ),
                        evidence_status=EvidenceStatus.VERIFIED,
                        cited_source="WCAG 2.1 AA 1.4.3 Contrast (Minimum)",
                        suggested_fix=f"Increase contrast to at least {threshold:.1f}:1",
                        human_review_required=True,
                    )
                )

    # 2. Missing Alt Text Check
    if acc_rules.require_alt_text and visual_metadata.has_alt_text is False:
        findings.append(
            Finding(
                finding_id="a11y_missing_alt_text",
                category=FindingCategory.VISUAL_WCAG,
                severity=FindingSeverity.MEDIUM,
                highlighted_text="Visual Asset / Image",
                text_span=TextSpan(start=0, end=0),
                explanation="Visual media is missing required descriptive alternative text.",
                evidence_status=EvidenceStatus.VERIFIED,
                cited_source="WCAG 2.1 AA 1.1.1 Non-text Content",
                suggested_fix="Provide descriptive alt text for screen readers",
                human_review_required=True,
            )
        )

    # 3. Logo Clear Space Check
    if visual_metadata.logo_clear_space_met is False:
        findings.append(
            Finding(
                finding_id="a11y_logo_clear_space",
                category=FindingCategory.VISUAL_WCAG,
                severity=FindingSeverity.LOW,
                highlighted_text="Brand Logo Margin",
                text_span=TextSpan(start=0, end=0),
                explanation="Brand logo violates configured minimum clear space perimeter.",
                evidence_status=EvidenceStatus.VERIFIED,
                cited_source="Brand Identity Guidelines: Logo Clear Space",
                suggested_fix="Increase padding around brand logo to meet guideline requirements",
                human_review_required=False,
            )
        )

    return findings
