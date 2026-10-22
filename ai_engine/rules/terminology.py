"""Deterministic terminology evaluator.

Checks draft content against approved product and brand names and flags
prohibited variants using exact character spans and word boundary safety.
"""

import re
from typing import List
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)


def evaluate_terminology(content_text: str, policy: BrandPolicy) -> List[Finding]:
    """Inspect text for prohibited brand terminology variants with word-boundary awareness.

    Avoids false positives inside unrelated words using lookaround assertions.
    """
    findings: List[Finding] = []

    for term in policy.approved_terminology:
        for variant in term.prohibited_variants:
            if not variant:
                continue

            escaped = re.escape(variant)
            # Use negative lookbehind/lookahead for word chars to handle hyphens and words accurately
            pattern = rf"(?<!\w){escaped}(?!\w)"
            flags = 0 if term.case_sensitive else re.IGNORECASE

            for match in re.finditer(pattern, content_text, flags):
                start, end = match.span()
                matched_text = content_text[start:end]
                replacement = term.replacement_suggestion or term.approved_term

                findings.append(
                    Finding(
                        finding_id=f"term_{term.term_id or 'rule'}_{start}_{end}",
                        category=FindingCategory.TERMINOLOGY,
                        severity=FindingSeverity.MEDIUM,
                        highlighted_text=matched_text,
                        text_span=TextSpan(start=start, end=end),
                        explanation=(
                            f"Prohibited brand variant '{matched_text}' detected. "
                            f"The approved brand spelling is '{term.approved_term}'."
                        ),
                        evidence_status=EvidenceStatus.VERIFIED,
                        suggested_fix=replacement,
                        human_review_required=False,
                    )
                )

    return findings
