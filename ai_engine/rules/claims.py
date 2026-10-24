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


def _phrase_regex(phrase: str) -> str:
    """Build a word-boundary-safe regex matching a phrase with flexible inner whitespace."""
    tokens = [re.escape(tok) for tok in re.split(r"\s+", phrase) if tok]
    return rf"(?<!\w){r'\s+'.join(tokens)}(?!\w)"


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
        # Generic default patterns applied only when the active brand policy
        # does not define its own superlative patterns.
        superlative_patterns = claims_policy.superlative_patterns or [
            "the best in the world",
            "world's best",
            "the world's best",
            "unbeatable",
            "second to none",
        ]

        for phrase in superlative_patterns:
            escaped = re.escape(phrase)
            pattern = rf"(?<!\w){escaped}(?!\w)"

            for match in re.finditer(pattern, content_text, re.IGNORECASE):
                start, end = match.span()
                matched_text = content_text[start:end]

                # Check if an authorized benchmark is provided in supplied evidence
                has_benchmark = any(
                    _has_applicable_benchmark(b.benchmark_id, supplied_evidence)
                    for b in claims_policy.permitted_benchmarks
                )

                if has_benchmark:
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
                    rule_ref = claims_policy.rule_reference or "the brand claims policy"
                    explanation = (
                        f"Unsupported superlative claim '{matched_text}'. Per {rule_ref}, "
                        "comparative superlatives require an authorized benchmark citation."
                    )
                    # No fabricated replacement: correction requires either a brand-supplied
                    # benchmark or reviewer-provided qualified wording.
                    fix = None

                findings.append(
                    Finding(
                        finding_id=f"claim_superlative_{start}_{end}",
                        category=FindingCategory.UNSUPPORTED_CLAIM,
                        severity=severity,
                        highlighted_text=matched_text,
                        text_span=TextSpan(start=start, end=end),
                        explanation=explanation,
                        evidence_status=evidence_status,
                        cited_source=f"{claims_policy.rule_reference or 'Claims Policy'}: Superlative Policy",
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

            # Check if the forbidden guarantee is contradicted by an authoritative
            # brand factual rule configured in the active policy (brand-agnostic:
            # the contradiction wording always comes from the brand's own data).
            conflicting_rule = next(
                (
                    rule
                    for rule in policy.factual_rules
                    if rule.is_active
                    and any(
                        prohibited.strip().lower() == phrase.strip().lower()
                        for prohibited in rule.prohibited_claims
                    )
                ),
                None,
            )
            if conflicting_rule is not None:
                category = FindingCategory.WRONG_FACT
                severity = FindingSeverity.CRITICAL
                status = EvidenceStatus.CONTRADICTED
                explanation = (
                    f"Contradicted claim '{matched_text}'. {conflicting_rule.rule_id} asserts "
                    f"the authoritative brand fact: '{conflicting_rule.approved_fact}'."
                )
                fix = conflicting_rule.suggested_correction or conflicting_rule.approved_fact
            else:
                category = FindingCategory.UNSUPPORTED_CLAIM
                severity = FindingSeverity.HIGH
                status = EvidenceStatus.UNSUPPORTED
                explanation = (
                    f"Absolute guarantee '{matched_text}' is prohibited by the active "
                    "brand claims policy."
                )
                fix = None

            cited_source = (
                f"Authoritative Brand Fact: {conflicting_rule.rule_id}"
                if conflicting_rule is not None
                else "Brand Guarantee Policy"
            )

            findings.append(
                Finding(
                    finding_id=f"claim_guarantee_{start}_{end}",
                    category=category,
                    severity=severity,
                    highlighted_text=matched_text,
                    text_span=TextSpan(start=start, end=end),                        explanation=explanation,
                        evidence_status=status,
                        cited_source=cited_source,
                    suggested_fix=fix,
                    human_review_required=True,
                )
            )

    # 3. Absolute Legal Claims (default absolute legal guarantees not covered by policy data)
    absolute_legal_claims = [
        "risk-free",
        "risk free",
        "fully compliant with every law",
    ]
    for phrase in absolute_legal_claims:
        pattern = _phrase_regex(phrase)

        for match in re.finditer(pattern, content_text, re.IGNORECASE):
            start, end = match.span()
            matched_text = content_text[start:end]
            findings.append(
                Finding(
                    finding_id=f"claim_legal_{start}_{end}",
                    category=FindingCategory.UNSUPPORTED_CLAIM,
                    severity=FindingSeverity.HIGH,
                    highlighted_text=matched_text,
                    text_span=TextSpan(start=start, end=end),
                    explanation=(
                        f"Absolute legal claim '{matched_text}' is prohibited by brand claims policy; "
                        "absolute legal guarantees cannot be substantiated for any brand."
                    ),
                    evidence_status=EvidenceStatus.UNSUPPORTED,
                    cited_source="Rule 4.2 Legal Claims Policy",
                    suggested_fix="rephrase with qualified, verifiable language",
                    human_review_required=True,
                )
            )

    # 4. Competitor Put-Downs
    # Single regex with optional "our" prefix avoids overlapping duplicate matches for
    # "our rivals are a joke" vs "rivals are a joke".
    competitor_putdown_patterns = [
        r"(?<!\w)(?:our\s+)?(?:rivals|competitors|competition)\s+are\s+a\s+joke(?!\w)",
    ]
    for pattern in competitor_putdown_patterns:
        for match in re.finditer(pattern, content_text, re.IGNORECASE):
            start, end = match.span()
            matched_text = content_text[start:end]
            findings.append(
                Finding(
                    finding_id=f"claim_putdown_{start}_{end}",
                    category=FindingCategory.TONE_MISMATCH,
                    severity=FindingSeverity.MEDIUM,
                    highlighted_text=matched_text,
                    text_span=TextSpan(start=start, end=end),
                    explanation=(
                        f"Competitor put-down '{matched_text}' violates brand tone policy "
                        "against disparaging rivals or competitors."
                    ),
                    evidence_status=EvidenceStatus.UNSUPPORTED,
                    cited_source="Rule 3.1 Tone Policy",
                    suggested_fix="Rephrase in a professional, objective brand voice without disparaging competitors.",
                    human_review_required=True,
                )
            )

    # 5. Standalone Guarantee with Exclamation (flags "guaranteed!", "Guaranteed!!")
    #    Uses an empty suggested_fix so RewriteAgent mechanically strips the token
    #    and the post-rewrite re-check stays clean.
    for match in re.finditer(r"(?<!\w)guaranteed!+(?!\w)", content_text, re.IGNORECASE):
        start, end = match.span()
        matched_text = content_text[start:end]
        findings.append(
            Finding(
                finding_id=f"claim_guarantee_bang_{start}_{end}",
                category=FindingCategory.UNSUPPORTED_CLAIM,
                severity=FindingSeverity.HIGH,
                highlighted_text=matched_text,
                text_span=TextSpan(start=start, end=end),
                explanation=(
                    f"Absolute guarantee '{matched_text}' is prohibited by brand claims policy; "
                    "absolute guarantees cannot be substantiated."
                ),
                evidence_status=EvidenceStatus.UNSUPPORTED,
                cited_source="Rule 4.2 Legal Claims Policy",
                suggested_fix="",
                human_review_required=True,
            )
        )

    return findings
