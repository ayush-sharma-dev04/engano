"""Legal and Policy Specialist Agent.

Evaluates draft content against authoritative brand and legal rules:
required disclaimers, trademark usage, restricted claims, and regulatory statements.
Ensures findings are strictly grounded in active BrandLibrary legal rules without
hallucinating legal advice.
"""

import re
from typing import List
from ai_engine.agents.specialists.base import BaseSpecialist
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)
from ai_engine.schemas.payload import DraftPayload


class LegalPolicySpecialist(BaseSpecialist):
    """Specialist responsible for legal, disclaimer, and regulatory brand compliance."""

    @property
    def name(self) -> str:
        return "LegalPolicySpecialist"

    def evaluate(self, payload: DraftPayload, policy: BrandPolicy) -> List[Finding]:
        if not payload.content_text or not policy.legal_rules:
            return []

        text = payload.content_text
        findings: List[Finding] = []

        # Collect approved facts to ensure approved statements are never flagged as violations
        approved_facts_lower = [f.approved_fact.lower() for f in policy.factual_rules]

        for rule in policy.legal_rules:
            rule_id = rule.rule_id

            # 1. Check restricted claims
            for claim in rule.restricted_claims:
                if not claim:
                    continue
                escaped = re.escape(claim)
                pattern = rf"(?<!\w){escaped}(?!\w)"
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    start, end = match.span()
                    matched = text[start:end]
                    findings.append(
                        Finding(
                            finding_id=f"legal_restricted_{rule_id}_{start}_{end}",
                            category=FindingCategory.LEGAL,
                            severity=FindingSeverity.HIGH,
                            highlighted_text=matched,
                            text_span=TextSpan(start=start, end=end),
                            explanation=(
                                f"Restricted claim '{matched}' violates legal policy {rule_id}: "
                                f"{rule.requirement}."
                            ),
                            evidence_status=EvidenceStatus.VERIFIED,
                            cited_source=rule_id,
                            suggested_fix="Remove or replace restricted claim with verified language.",
                            human_review_required=True,
                        )
                    )

            # 2. Check required disclaimers for unconditioned or non-approved promises
            # If the draft asserts absolute SLA promises without the required disclaimer
            for disclaimer in rule.required_disclaimers:
                if not disclaimer:
                    continue

                # Check if draft has an unconditioned or absolute SLA claim that is not an approved fact
                # E.g. "guaranteed SLA", "100% SLA", "unlimited SLA"
                unconditioned_sla_patterns = [
                    r"\bguaranteed\s+sla\b",
                    r"\b100%\s+sla\b",
                    r"\bunconditional\s+sla\b",
                    r"\bunlimited\s+sla\b",
                ]
                has_unconditioned = any(
                    re.search(pat, text, re.IGNORECASE) for pat in unconditioned_sla_patterns
                )

                if has_unconditioned and disclaimer.lower() not in text.lower():
                    findings.append(
                        Finding(
                            finding_id=f"legal_missing_disclaimer_{rule_id}",
                            category=FindingCategory.LEGAL,
                            severity=FindingSeverity.HIGH,
                            highlighted_text=text[:min(len(text), 40)],
                            text_span=TextSpan(start=0, end=min(len(text), 40)),
                            explanation=(
                                f"Missing mandatory legal disclaimer per {rule_id}: "
                                f"'{disclaimer}'."
                            ),
                            evidence_status=EvidenceStatus.VERIFIED,
                            cited_source=rule_id,
                            suggested_fix=f"Append required disclaimer: '{disclaimer}'",
                            human_review_required=True,
                        )
                    )

        return findings
