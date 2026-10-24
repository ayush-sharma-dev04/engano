"""Deterministic factual evaluator.

Evaluates draft content against authoritative brand facts, validity dates,
pricing, and promotional offers.
"""

from datetime import date
import re
from typing import List, Optional
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)


def evaluate_factual(
    content_text: str,
    policy: BrandPolicy,
    current_date: Optional[date] = None,
) -> List[Finding]:
    """Check draft content against authoritative brand facts and active offers."""
    findings: List[Finding] = []
    eval_date = current_date or date.today()

    # Resolve currently active offer names from the brand's own policy data
    # (brand-agnostic: never fabricate an example offer for the brand).
    active_offer_names = [
        offer.name
        for offer in policy.offers
        if not (offer.is_retired or (offer.validity_end and eval_date > offer.validity_end))
        and offer.name
    ]
    active_offer_hint = (
        f" Active offers: {', '.join(active_offer_names)}."
        if active_offer_names
        else " No active offer is currently configured."
    )

    # 1. Inspect Offers (Active vs Retired / Expired)
    for offer in policy.offers:
        is_expired = offer.validity_end and eval_date > offer.validity_end
        is_inactive = offer.is_retired or is_expired

        # Check phrases associated with this offer
        phrases_to_check = list(offer.prohibited_phrases)
        if is_inactive:
            phrases_to_check.append(offer.name)

        for phrase in set(phrases_to_check):
            if not phrase:
                continue
            escaped = re.escape(phrase)
            pattern = rf"(?<!\w){escaped}(?!\w)"

            for match in re.finditer(pattern, content_text, re.IGNORECASE):
                start, end = match.span()
                matched_text = content_text[start:end]

                if is_inactive:
                    findings.append(
                        Finding(
                            finding_id=f"offer_retired_{offer.offer_id}_{start}_{end}",
                            category=FindingCategory.OUTDATED_OFFER,
                            severity=FindingSeverity.HIGH,
                            highlighted_text=matched_text,
                            text_span=TextSpan(start=start, end=end),
                        explanation=(
                            f"The promotional offer '{matched_text}' has been retired "
                            f"(valid until {offer.validity_end or 'past'}).{active_offer_hint}"
                        ),
                        evidence_status=EvidenceStatus.CONTRADICTED,
                        cited_source=f"Brand Offer Catalog: {offer.offer_id}",
                        suggested_fix=(
                            active_offer_names[0] if active_offer_names else None
                        ),
                            human_review_required=True,
                        )
                    )

    # 2. Inspect Factual Rules & Prohibited Contradictions
    for rule in policy.factual_rules:
        # Check if rule is currently active
        is_active = rule.is_active
        if rule.validity_end and eval_date > rule.validity_end:
            is_active = False
        if rule.validity_start and eval_date < rule.validity_start:
            is_active = False

        if not is_active:
            continue

        for prohibited in rule.prohibited_claims:
            if not prohibited:
                continue
            escaped = re.escape(prohibited)
            pattern = rf"(?<!\w){escaped}(?!\w)"

            for match in re.finditer(pattern, content_text, re.IGNORECASE):
                start, end = match.span()
                matched_text = content_text[start:end]

                findings.append(
                    Finding(
                        finding_id=f"fact_contradiction_{rule.rule_id}_{start}_{end}",
                        category=FindingCategory.WRONG_FACT,
                        severity=FindingSeverity.CRITICAL,
                        highlighted_text=matched_text,
                        text_span=TextSpan(start=start, end=end),
                        explanation=(
                            f"Content asserts '{matched_text}' which contradicts authoritative fact: "
                            f"'{rule.approved_fact}'."
                        ),
                        evidence_status=EvidenceStatus.CONTRADICTED,
                        cited_source=f"Authoritative Brand Fact: {rule.rule_id}",
                        suggested_fix=rule.approved_fact,
                        human_review_required=True,
                    )
                )

    return findings
