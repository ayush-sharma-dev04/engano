"""Public review interface schemas.

Defines the contract for requests, decisions, metadata, and final results
consumed by the engine orchestrator and backend services.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ai_engine.schemas.findings import Finding


class ReviewDecision(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class ActionRequiredBy(str, Enum):
    NONE = "none"
    CREATOR_ONE_CLICK_CORRECTION = "creator_one_click_correction"
    CREATOR_CLARIFICATION = "creator_clarification"
    REVIEWER_APPROVAL = "reviewer_approval"


class DecisionOutcome(BaseModel):
    """Overall review decision and action assignment."""
    status: ReviewDecision = Field(description="Review decision outcome: GREEN, YELLOW, or RED")
    action_required_by: ActionRequiredBy = Field(
        default=ActionRequiredBy.NONE,
        description="Actor required to resolve findings"
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="Clarification question when creator clarification is needed"
    )
    reason: str = Field(description="Summary explanation for the decision")


class VisualMetadata(BaseModel):
    """Optional visual and accessibility metadata provided for Web Studio assets."""
    contrast_ratio: Optional[float] = Field(default=None, ge=1.0, le=21.0, description="Measured contrast ratio against background")
    is_large_text: bool = Field(default=False, description="True if text size is >= 18pt or 14pt bold")
    has_alt_text: Optional[bool] = Field(default=None, description="True if alternative text is provided for imagery")
    logo_clear_space_met: Optional[bool] = Field(default=None, description="True if required logo margins are respected")


class ReviewInput(BaseModel):
    """Review request input for Web Studio content."""
    draft_id: str = Field(description="Unique draft identifier")
    brand_id: str = Field(description="Brand identifier to load authoritative policy")
    content_text: str = Field(description="Draft copy to review")
    supplied_evidence: Optional[Any] = Field(
        default=None,
        description="Optional evidence provided by creator (benchmarks, citations)"
    )
    visual_metadata: Optional[VisualMetadata] = Field(
        default=None,
        description="Optional accessibility and visual measurements"
    )


class ProcessingMetadata(BaseModel):
    """Execution metadata detailing providers and agents invoked."""
    provider_selected: str = Field(description="Provider executed: rules_only, gemini, ollama")
    agents_executed: List[str] = Field(default_factory=list, description="List of agent stages executed")
    processing_time_ms: float = Field(default=0.0, description="Processing duration in milliseconds")
    fallback_occurred: bool = Field(default=False, description="True if safe fallback was triggered")
    fallback_details: Optional[str] = Field(default=None, description="Details explaining fallback event")


class ReviewResult(BaseModel):
    """Comprehensive review result returned by run_brand_review."""
    draft_id: str
    brand_id: str
    completion_status: str = Field(
        default="completed",
        description="Execution status: completed, incomplete_policy, operational_failure"
    )
    decision: DecisionOutcome
    findings: List[Finding] = Field(default_factory=list)
    proposed_rewrite: Optional[str] = Field(
        default=None,
        description="Safe proposed correction with minimal changes"
    )
    metadata: ProcessingMetadata
