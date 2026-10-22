"""Governance Analysis Agent.

Analyzes review outcomes, human overrides, and dismissal patterns to recommend
brand policy improvements.
STRICT SAFETY CONTRACT: Never automatically modifies Supabase policies or mutates
production rules without human administrator approval.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ai_engine.schemas.findings import Finding, FindingCategory


class GovernanceRecommendation(BaseModel):
    """Advisory recommendation for brand policy administrators."""
    recommendation_id: str
    target_rule_or_category: str
    advisory_notice: str
    requires_human_approval: bool = True
    proposed_action: str


class GovernanceReport(BaseModel):
    """Comprehensive governance feedback report."""
    total_findings_analyzed: int
    recurring_gap_categories: List[str] = Field(default_factory=list)
    recommendations: List[GovernanceRecommendation] = Field(default_factory=list)
    has_historical_override_data: bool = False
    data_limitation_notice: Optional[str] = None


class GovernanceAgent:
    """Agent that generates non-mutating governance insights and policy advice."""

    def analyze_review_outcomes(
        self,
        current_findings: List[Finding],
        historical_overrides: Optional[List[Dict[str, Any]]] = None,
    ) -> GovernanceReport:
        """Analyze current review findings and optional override logs.

        Does NOT mutate database or active policies.
        """
        recs: List[GovernanceRecommendation] = []
        categories = [f.category for f in current_findings]

        if historical_overrides is None or len(historical_overrides) == 0:
            data_notice = (
                "Historical dismissal and human override records are currently unavailable. "
                "Governance recommendations are limited to draft findings analysis."
            )
            has_overrides = False
        else:
            data_notice = None
            has_overrides = True

        # Identify recurring gaps in current draft
        recurring_categories: List[str] = []
        for cat in set(categories):
            count = categories.count(cat)
            if count >= 2:
                recurring_categories.append(cat.value)
                recs.append(
                    GovernanceRecommendation(
                        recommendation_id=f"gov_rec_{cat.value}",
                        target_rule_or_category=cat.value,
                        advisory_notice=(
                            f"Multiple ({count}) findings detected in category '{cat.value}'. "
                            "Consider publishing explicit author guidance in Web Studio."
                        ),
                        requires_human_approval=True,
                        proposed_action="Review author guideline clarity (Requires Human Approval)",
                    )
                )

        return GovernanceReport(
            total_findings_analyzed=len(current_findings),
            recurring_gap_categories=recurring_categories,
            recommendations=recs,
            has_historical_override_data=has_overrides,
            data_limitation_notice=data_notice,
        )
