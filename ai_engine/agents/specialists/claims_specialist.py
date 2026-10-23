"""Claims Specialist Agent.

Evaluates comparative superlatives, factual statements against approved facts,
SLA commitments, and promotional offer validity.
Strictly distinguishes missing evidence (unsupported) from proven falsehood (contradicted).
"""

from datetime import date
from typing import List, Optional
from ai_engine.agents.specialists.base import BaseSpecialist
from ai_engine.rules.claims import evaluate_claims
from ai_engine.rules.factual import evaluate_factual
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
)
from ai_engine.schemas.payload import DraftPayload


class ClaimsSpecialist(BaseSpecialist):
    """Specialist responsible for factual veracity, claims, and offer status."""

    def __init__(self, current_date: Optional[date] = None) -> None:
        self.current_date = current_date

    @property
    def name(self) -> str:
        return "ClaimsSpecialist"

    def evaluate(self, payload: DraftPayload, policy: BrandPolicy) -> List[Finding]:
        if not payload.content_text:
            return []

        text = payload.content_text
        findings: List[Finding] = []

        # 1. Evaluate superlatives and guarantees using existing claims rules
        claim_findings = evaluate_claims(
            content_text=text,
            policy=policy,
            supplied_evidence=payload.supplied_evidence,
        )
        for cf in claim_findings:
            # Ensure superlative without benchmark is strictly unsupported, not contradicted
            if cf.category == FindingCategory.UNSUPPORTED_CLAIM:
                cf = cf.model_copy(update={
                    "evidence_status": EvidenceStatus.UNSUPPORTED,
                    "human_review_required": True,
                })
            findings.append(cf)

        # 2. Evaluate factual contradictions and expired/retired offers
        factual_findings = evaluate_factual(
            content_text=text,
            policy=policy,
            current_date=self.current_date,
        )
        for ff in factual_findings:
            # Contradicted approved facts or retired offers require reviewer approval
            if ff.category in (FindingCategory.WRONG_FACT, FindingCategory.OUTDATED_OFFER):
                ff = ff.model_copy(update={
                    "evidence_status": EvidenceStatus.CONTRADICTED,
                    "human_review_required": True,
                })
            findings.append(ff)

        return findings
