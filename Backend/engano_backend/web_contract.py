"""Web Studio API contract.

Frontend 02 (`Frontend 02/src/App.tsx`) calls two endpoints that this module
defines the request/response contract for:

- ``POST {VITE_AI_API_URL}/review``          -> { findings, confidence, needsHumanReview, ... }
- ``POST {VITE_AI_API_URL}/creator/improve`` -> { improvedContent, suggestions?, ... }

The authoritative brand policy is always resolved server-side from the
configured policy repository. Client-supplied ``guidelines`` payloads are
accepted for compatibility and echoed as advisory context only; they are
never used as authoritative policy, mirroring the adapter-layer rule that the
brand "always comes from our settings, never from the sender's message".
"""

import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_engine.schemas.findings import Finding
from ai_engine.schemas.review import ReviewDecision, ReviewResult

from .review_service import category_label

SEVERITY_TIER: Dict[str, str] = {
    "critical": "Critical",
    "high": "Critical",
    "medium": "Warning",
    "low": "Suggestion",
}

# Mirrors the demo thresholds the Web Studio already renders
# (critical -> 55, warnings -> 72, clean -> 94; < 80 triggers human review).
DECISION_CONFIDENCE: Dict[str, int] = {
    "GREEN": 94,
    "YELLOW": 72,
    "RED": 55,
}


def new_draft_id() -> str:
    return str(uuid.uuid4())




class WebReviewRequest(BaseModel):
    """Request body for POST /review (authoritative policy is server-side)."""

    draft_id: Optional[str] = None
    brand_id: Optional[str] = None
    title: Optional[str] = None
    content: str
    # Advisory only. Never treated as authoritative policy.
    guidelines: Optional[List[Any]] = None

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("content must not be blank")
        return value.strip()

    model_config = ConfigDict(extra="forbid")


class CreatorImproveRequest(BaseModel):
    """Request body for POST /creator/improve (demo contract preserved)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    content: str
    platform: str = "web"
    auto_spelling: bool = Field(default=False, alias="autoSpelling")
    auto_grammar: bool = Field(default=False, alias="autoGrammar")

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("content must not be blank")
        return value.strip()


def finding_to_finding_dict(finding: Finding) -> Dict[str, Any]:
    """Map an engine Finding to the Web Studio finding shape."""
    return {
        "severity": SEVERITY_TIER.get(finding.severity.value, "Suggestion"),
        "category": category_label(finding.category.value),
        "issue": finding.explanation.split(". ")[0][:140],
        "explanation": finding.explanation,
        "guideline": finding.cited_source or "",
        "suggestion": finding.suggested_fix or "",
        # Engine detail retained for richer UI use later.
        "finding_id": finding.finding_id,
        "evidence_status": finding.evidence_status.value,
        "human_review_required": finding.human_review_required,
    }


def response_fields(result: ReviewResult) -> Dict[str, Any]:
    """Confidence/needsHumanReview fields derived from the decision."""
    confidence = DECISION_CONFIDENCE[result.decision.status.value]
    needs_human_review = result.decision.status in (ReviewDecision.RED, ReviewDecision.YELLOW)
    return {"confidence": confidence, "needsHumanReview": needs_human_review}


def web_review_response(result: ReviewResult) -> Dict[str, Any]:
    """Full POST /review response in the Web Studio contract."""
    return {
        "draft_id": result.draft_id,
        "brand_id": result.brand_id,
        "status": result.decision.status.value,
        "completion_status": result.completion_status,
        **response_fields(result),
        "decision": {
            "status": result.decision.status.value,
            "action_required_by": result.decision.action_required_by.value,
            "reason": result.decision.reason,
            "clarification_question": result.decision.clarification_question,
        },
        "findings": [finding_to_finding_dict(f) for f in result.findings],
        "suggested_full_rewrite": result.proposed_rewrite,
        "metadata": {
            "provider": result.metadata.provider_selected,
            "policy_source": result.metadata.policy_source,
            "fallback_occurred": result.metadata.fallback_occurred,
        },
    }


def creator_improve_response(result: ReviewResult, request: CreatorImproveRequest) -> Dict[str, Any]:
    """POST /creator/improve response in the Web Studio contract.

    Only a rewrite that survived the engine's own post-rewrite revalidation is
    offered as improved content; otherwise the original draft is returned with
    actionable suggestions.
    """
    improved = request.content.strip()
    rewrite_ok = (
        result.decision.status in (ReviewDecision.RED, ReviewDecision.YELLOW)
        and result.proposed_rewrite is not None
        and result.post_rewrite_decision is not None
        and result.post_rewrite_decision.status == ReviewDecision.GREEN
    )
    if rewrite_ok:
        improved = result.proposed_rewrite

    suggestions: List[str] = []
    for finding in result.findings:
        if finding.suggested_fix:
            label = category_label(finding.category.value)
            suggestions.append(f"{label}: {finding.suggested_fix}")
        if len(suggestions) >= 3:
            break

    return {
        "improvedContent": improved,
        "suggestions": suggestions,
        "platform": request.platform,
        "rewriteApplied": rewrite_ok,
        **response_fields(result),
    }
