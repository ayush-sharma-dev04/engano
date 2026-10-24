"""Tone Specialist Agent.

Evaluates draft copy against active brand voice and style guidelines.
Checks for tone mismatch, aggressive hype, unverified boasting, or style violations
grounded in the active BrandLibrary tone rules.
"""

import re
from typing import List, Optional
from ai_engine.agents.specialists.base import BaseSpecialist
from ai_engine.providers.base import BaseProvider
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)
from ai_engine.schemas.payload import DraftPayload


# Common aggressive hype indicators checked deterministically when tone rules prohibit hype
_HYPE_PATTERNS = [
    (r"\b(crushes|destroys|obliterates)\s+the\s+competition\b", "Aggressive competitive rhetoric"),
    (r"\b(insane|mind[- ]blowing|crazy)\s+(speed|performance|power)\b", "Hyperbolic claim"),
    (r"!{2,}", "Excessive exclamation marks"),
    (r"\b(unbeatable|unrivaled|magical)\b", "Unsubstantiated boasting"),
]


class ToneSpecialist(BaseSpecialist):
    """Specialist responsible for brand voice, style, and tone compliance."""

    def __init__(self, provider: Optional[BaseProvider] = None) -> None:
        self.provider = provider

    @property
    def name(self) -> str:
        return "ToneSpecialist"

    def evaluate(self, payload: DraftPayload, policy: BrandPolicy) -> List[Finding]:
        if not payload.content_text or not policy.tone_rules:
            return []

        text = payload.content_text
        findings: List[Finding] = []

        # 1. Deterministic tone rule checks against configured prohibited tones
        for rule in policy.tone_rules:
            rule_ref = rule.rule_id or "Rule 3.1"
            prohibited_lowered = [t.lower() for t in rule.prohibited_tones]

            # Check if hype or aggressive boasting is prohibited in this brand policy
            hype_prohibited = any(
                "hype" in p or "boasting" in p or "aggressive" in p
                for p in prohibited_lowered
            )

            if hype_prohibited:
                for pattern, desc in _HYPE_PATTERNS:
                    for match in re.finditer(pattern, text, re.IGNORECASE):
                        start, end = match.span()
                        matched = text[start:end]
                        findings.append(
                            Finding(
                                finding_id=f"tone_{rule_ref.replace(' ', '_').lower()}_{start}_{end}",
                                category=FindingCategory.TONE_MISMATCH,
                                severity=FindingSeverity.MEDIUM,
                                highlighted_text=matched,
                                text_span=TextSpan(start=start, end=end),
                                explanation=(
                                    f"Tone violation detected: '{matched}' reflects {desc.lower()}, "
                                    f"which conflicts with {rule_ref} ({rule.description or 'prohibited tone'})."
                                ),
                                evidence_status=EvidenceStatus.VERIFIED,
                                cited_source=rule_ref,
                                suggested_fix=(
                                    "!" if set(matched) == {"!"}
                                    else "Rephrase in a clear, professional, and objective brand voice."
                                ),
                                human_review_required=False,
                            )
                        )

            # Check direct phrase matches in prohibited_tones if specific phrases are provided
            for prob_tone in rule.prohibited_tones:
                if len(prob_tone.split()) > 1 and prob_tone.lower() in text.lower():
                    idx = text.lower().find(prob_tone.lower())
                    start = idx
                    end = idx + len(prob_tone)
                    findings.append(
                        Finding(
                            finding_id=f"tone_direct_{rule_ref.replace(' ', '_').lower()}_{start}",
                            category=FindingCategory.TONE_MISMATCH,
                            severity=FindingSeverity.MEDIUM,
                            highlighted_text=text[start:end],
                            text_span=TextSpan(start=start, end=end),
                            explanation=(
                                f"Text contains '{text[start:end]}', matching prohibited tone '{prob_tone}' "
                                f"per {rule_ref}."
                            ),
                            evidence_status=EvidenceStatus.VERIFIED,
                            cited_source=rule_ref,
                            suggested_fix="Revise to align with approved brand tone.",
                            human_review_required=False,
                        )
                    )

        return findings
