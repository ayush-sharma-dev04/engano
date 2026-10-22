"""Evidence Validation Agent.

Evaluates claims against authoritative facts and user-supplied evidence.
Distinguishes verified, unsupported, contradicted, and unverified user-provided evidence
without fabricating source citations.
"""

from typing import Any, List, Optional
from pydantic import BaseModel
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import EvidenceStatus, Finding, FindingCategory


class ClaimValidationReport(BaseModel):
    """Validation report summarizing evidence status of evaluated claims."""
    total_claims: int
    verified_count: int
    unsupported_count: int
    contradicted_count: int
    unverified_provided_count: int


class EvidenceValidationAgent:
    """Agent for rigorous validation of claim-evidence relationships."""

    def validate_findings(
        self,
        findings: List[Finding],
        policy: BrandPolicy,
        supplied_evidence: Optional[Any] = None,
    ) -> List[Finding]:
        """Validate and classify evidence status for all findings."""
        validated: List[Finding] = []

        for finding in findings:
            updated = finding.model_copy()

            # Skip categories that are deterministic syntax/visual checks
            if finding.category in (FindingCategory.TERMINOLOGY, FindingCategory.VISUAL_WCAG):
                validated.append(updated)
                continue

            # Evaluate against authoritative facts
            text_lowered = finding.highlighted_text.lower()

            # Check if contradicted by an active fact or retired offer
            is_contradicted = False
            for fact in policy.factual_rules:
                if any(p.lower() in text_lowered for p in fact.prohibited_claims):
                    updated.evidence_status = EvidenceStatus.CONTRADICTED
                    updated.cited_source = f"Authoritative SLA Fact: {fact.rule_id}"
                    is_contradicted = True
                    break

            for offer in policy.offers:
                if offer.is_retired and (offer.name.lower() in text_lowered or any(p.lower() in text_lowered for p in offer.prohibited_phrases)):
                    updated.evidence_status = EvidenceStatus.CONTRADICTED
                    updated.cited_source = f"Brand Offer Catalog: {offer.offer_id} (Retired)"
                    is_contradicted = True
                    break

            if is_contradicted:
                validated.append(updated)
                continue

            # If evidence was supplied by the creator
            if supplied_evidence:
                evidence_str = str(supplied_evidence).lower()
                # Check if supplied evidence specifically addresses this finding
                if text_lowered in evidence_str or any(word in evidence_str for word in text_lowered.split() if len(word) > 4):
                    # Supplied evidence provided, but unverified by independent official records
                    updated.evidence_status = EvidenceStatus.UNVERIFIED_PROVIDED
                else:
                    updated.evidence_status = EvidenceStatus.UNSUPPORTED
            else:
                # No evidence supplied at all
                if updated.evidence_status != EvidenceStatus.CONTRADICTED:
                    updated.evidence_status = EvidenceStatus.UNSUPPORTED

            validated.append(updated)

        return validated

    def summarize_evidence(self, findings: List[Finding]) -> ClaimValidationReport:
        """Produce summary counts of evidence statuses."""
        claim_findings = [
            f for f in findings
            if f.category in (FindingCategory.UNSUPPORTED_CLAIM, FindingCategory.WRONG_FACT, FindingCategory.OUTDATED_OFFER)
        ]
        return ClaimValidationReport(
            total_claims=len(claim_findings),
            verified_count=sum(1 for f in claim_findings if f.evidence_status == EvidenceStatus.VERIFIED),
            unsupported_count=sum(1 for f in claim_findings if f.evidence_status == EvidenceStatus.UNSUPPORTED),
            contradicted_count=sum(1 for f in claim_findings if f.evidence_status == EvidenceStatus.CONTRADICTED),
            unverified_provided_count=sum(1 for f in claim_findings if f.evidence_status == EvidenceStatus.UNVERIFIED_PROVIDED),
        )
