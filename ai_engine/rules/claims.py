"""Deterministic claims evaluator.

Detects superlatives, unapproved guarantees, and absolute claims,
evaluating them against policy rules and optional supplied evidence.
"""

import re
from typing import Any, List, Optional
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)


def _has_applicable_benchmark(benchmark_id: str, supplied_evidence: Optional[Any]) -> bool:
    """Check if the required benchmark is cited in supplied evidence."""
    if not supplied_evidence:
        return False
    if isinstance(supplied_evidence, str):
        return benchmark_id.lower() in supplied_evidence.lower()
    if isinstance(supplied_evidence, (list, dict)):
        serialized = str(supplied_evidence).lower()
        return benchmark_id.lower() in serialized
    return False


def evaluate_claims(
    content_text: str,
    policy: BrandPolicy,
    supplied_evidence: Optional[Any] = None,
) -> List[Finding]:
    """Inspect text for superlative claims and forbidden guarantees."""
    findings: List[Finding] = []
    claims_policy = policy.claims_policy

    # 1. Superlative Claims
    if claims_policy.superlatives_require_benchmark:
        superlative_patterns = claims_policy.superlative_patterns or [
            "fastest database in the world",
            "fastest database",
            "best in the world",
            "best database in the world",
            "highest performance",
        ]

        for phrase in superlative_patterns:
            escaped = re.escape(phrase)
            pattern = rf"(?<!\w){escaped}(?!\w)"

            for match in re.finditer(pattern, content_text, re.IGNORECASE):
                start, end = match.span()
                matched_text = content_text[start:end]

                # Check if an authorized benchmark is provided in supplied evidence
                has_b4 = any(
                    _has_applicable_benchmark(b.benchmark_id, supplied_evidence)
                    for b in claims_policy.permitted_benchmarks
                )

                if has_b4:
                    evidence_status = EvidenceStatus.UNVERIFIED_PROVIDED
                    severity = FindingSeverity.LOW
                    explanation = (
                        f"Superlative '{matched_text}' references supplied benchmark evidence "
                        "which requires reviewer verification."
                    )
                    fix = None
                else:
                    evidence_status = EvidenceStatus.UNSUPPORTED
                    severity = FindingSeverity.HIGH
                    rule_ref = claims_policy.rule_reference or "claims policy"
                    explanation = (
                        f"Unsupported superlative claim '{matched_text}'. Per {rule_ref}, "
                        "comparative superlatives require an authorized benchmark citation."
                    )
                    fix = "high-performance database"

                findings.append(
                    Finding(
                        finding_id=f"claim_superlative_{start}_{end}",
                        category=FindingCategory.UNSUPPORTED_CLAIM,
                        severity=severity,
                        highlighted_text=matched_text,
                        text_span=TextSpan(start=start, end=end),
                        explanation=explanation,
                        evidence_status=evidence_status,
                        cited_source="Rule 4.2 Superlative Policy",
                        suggested_fix=fix,
                        human_review_required=True,
                    )
                )

    # 2. Forbidden Guarantees & Absolute Claims
    forbidden_guarantees = claims_policy.forbidden_guarantees or [
        "100% uptime",
        "guaranteed results",
        "zero downtime",
    ]

    for phrase in forbidden_guarantees:
        escaped = re.escape(phrase)
        pattern = rf"(?<!\w){escaped}(?!\w)"

        for match in re.finditer(pattern, content_text, re.IGNORECASE):
            start, end = match.span()
            matched_text = content_text[start:end]

            # Check if this guarantee conflicts with SLA fact
            is_uptime = "100%" in phrase.lower() and "uptime" in phrase.lower()
            if is_uptime:
                category = FindingCategory.WRONG_FACT
                severity = FindingSeverity.CRITICAL
                status = EvidenceStatus.CONTRADICTED
                explanation = (
                    f"Contradicted claim '{matched_text}'. Nimbus SLA guarantees 99.95% monthly uptime. "
                    "Absolute 100% uptime promises are prohibited."
                )
                fix = "99.95% uptime SLA"
            else:
                category = FindingCategory.UNSUPPORTED_CLAIM
                severity = FindingSeverity.HIGH
                status = EvidenceStatus.UNSUPPORTED
                explanation = f"Absolute guarantee '{matched_text}' is prohibited by brand claims policy."
                fix = "proven results"

            findings.append(
                Finding(
                    finding_id=f"claim_guarantee_{start}_{end}",
                    category=category,
                    severity=severity,
                    highlighted_text=matched_text,
                    text_span=TextSpan(start=start, end=end),
                    explanation=explanation,
                    evidence_status=status,
                    cited_source="Brand Guarantee Policy",
                    suggested_fix=fix,
                    human_review_required=True,
                )
            )

    return findings
