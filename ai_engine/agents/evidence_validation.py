"""Evidence Validation Agent.

Evaluates claims against authoritative facts and user-supplied evidence.
Distinguishes verified, unsupported, contradicted, and unverified user-provided evidence
without fabricating source citations.
"""

from typing import Any, List, Optional, Set
import re
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


_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?|[a-z]+")


def _claim_tokens(text: str) -> Set[str]:
    """Extract significant claim tokens (numbers and words >= 3 chars) from text."""
    return {tok for tok in _TOKEN_RE.findall(text.lower()) if len(tok) >= 3}


def _materially_supported_by_fact(
    highlight: str,
    approved_facts_lower: List[str],
    approved_fact_tokens: List[Set[str]],
    subject_tokens: Set[str],
) -> bool:
    """Return True if a finding's highlighted claim materially restates an approved fact."""
    if len(highlight) < 10 or highlight in subject_tokens:
        return False
    highlight_tokens = _claim_tokens(highlight)
    if not highlight_tokens:
        return False
    for fact, fact_tokens in zip(approved_facts_lower, approved_fact_tokens):
        if highlight in fact:
            return True
        if highlight_tokens and fact_tokens and highlight_tokens.issubset(fact_tokens):
            return True
    return False


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

        # Authoritative approved facts used to suppress AI false-positive findings that
        # merely restate the brand's own approved fact (e.g. AI flags "99.95% uptime SLA"
        # as an unverified claim). Never suppress solely for naming the same subject
        # (brand name / approved term) or short tokens.
        approved_facts_lower = [
            fr.approved_fact.lower().strip()
            for fr in policy.factual_rules
            if fr.is_active and fr.approved_fact
        ]
        approved_fact_tokens: List[Set[str]] = [
            _claim_tokens(f) for f in approved_facts_lower
        ]
        subject_tokens = {
            policy.brand_name.lower().strip(),
            *(term.approved_term.lower().strip() for term in policy.approved_terminology),
        }

        for finding in findings:
            updated = finding.model_copy()

            # Skip categories that are deterministic syntax/visual checks
            if finding.category in (FindingCategory.TERMINOLOGY, FindingCategory.VISUAL_WCAG):
                validated.append(updated)
                continue

            # Evaluate against authoritative facts
            text_lowered = finding.highlighted_text.lower()

            # Suppress findings whose specific claim materially matches an approved fact.
            # This targets AI-generated false positives without dropping genuine
            # contradictions, unsupported claims, or deterministic findings.
            highlight_stripped = text_lowered.strip()
            if _materially_supported_by_fact(
                highlight_stripped, approved_facts_lower, approved_fact_tokens, subject_tokens
            ):
                continue

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
