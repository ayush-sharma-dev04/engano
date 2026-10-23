"""Public review interface schemas.

Defines the contract for requests, decisions, metadata, and final results
consumed by the engine orchestrator and backend services.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ai_engine.schemas.findings import Finding
from ai_engine.schemas.payload import (
    ChannelType,
    DraftPayload,
    ImageItem,
    VisualMetadata,
)


class ReviewDecision(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class ActionRequiredBy(str, Enum):
    NONE = "none"
    CREATOR_ONE_CLICK = "creator_one_click"
    CREATOR_QUESTION = "creator_question"
    REVIEWER_APPROVAL = "reviewer_approval"
    # Backward compatibility aliases
    CREATOR_ONE_CLICK_CORRECTION = "creator_one_click"
    CREATOR_CLARIFICATION = "creator_question"

    @classmethod
    def _missing_(cls, value: object):
        if value in ("creator_one_click_correction", "creator_one_click"):
            return cls.CREATOR_ONE_CLICK
        if value in ("creator_clarification", "creator_question"):
            return cls.CREATOR_QUESTION
        return super()._missing_(value)


class DecisionOutcome(BaseModel):
    """Overall review decision and action assignment."""
    status: ReviewDecision = Field(description="Review decision outcome: GREEN, YELLOW, or RED")
    action_required_by: ActionRequiredBy = Field(
        default=ActionRequiredBy.NONE,
        description="Actor required to resolve findings",
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="Clarification question when creator clarification is needed",
    )
    reason: str = Field(description="Summary explanation for the decision")


class ReviewInput(DraftPayload):
    """Review request input for Web Studio content and backward-compatible intake."""
    channel: ChannelType = Field(default=ChannelType.WEB_STUDIO, description="Originating channel")


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
        description="Execution status: completed, incomplete_policy, operational_failure",
    )
    decision: DecisionOutcome
    findings: List[Finding] = Field(default_factory=list)
    proposed_rewrite: Optional[str] = Field(
        default=None,
        description="Safe proposed correction with minimal changes",
    )
    original_text: Optional[str] = Field(
        default=None,
        description="Original draft copy evaluated by the engine",
    )
    rewrite_proposal: Optional[Any] = Field(
        default=None,
        description="Detailed rewrite proposal and post-revalidation outcome",
    )
    post_rewrite_findings: List[Finding] = Field(
        default_factory=list,
        description="Findings remaining or introduced after revalidation of proposed rewrite",
    )
    post_rewrite_decision: Optional[DecisionOutcome] = Field(
        default=None,
        description="Decision outcome for proposed rewrite",
    )
    metadata: ProcessingMetadata
