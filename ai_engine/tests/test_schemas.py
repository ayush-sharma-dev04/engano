"""Tests for Pydantic v2 schemas and validation contracts."""

import pytest
from pydantic import ValidationError
from ai_engine.schemas.brand_policy import ApprovedTerm, BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)
from ai_engine.schemas.review import (
    ActionRequiredBy,
    DecisionOutcome,
    ProcessingMetadata,
    ReviewDecision,
    ReviewInput,
    ReviewResult,
    VisualMetadata,
)


def test_text_span_valid():
    span = TextSpan(start=0, end=10)
    assert span.start == 0
    assert span.end == 10


def test_text_span_invalid_order():
    with pytest.raises(ValidationError):
        TextSpan(start=10, end=5)


def test_text_span_negative_index():
    with pytest.raises(ValidationError):
        TextSpan(start=-1, end=5)


def test_finding_validate_against_text():
    full_text = "NimbusDB is fast."
    finding = Finding(
        finding_id="f1",
        category=FindingCategory.TERMINOLOGY,
        severity=FindingSeverity.MEDIUM,
        highlighted_text="NimbusDB",
        text_span=TextSpan(start=0, end=8),
        explanation="Prohibited variant",
        evidence_status=EvidenceStatus.VERIFIED,
        suggested_fix="Nimbus DB",
    )
    assert finding.validate_against_text(full_text) is True


def test_finding_validate_against_text_mismatch():
    full_text = "NimbusDB is fast."
    finding = Finding(
        finding_id="f1",
        category=FindingCategory.TERMINOLOGY,
        severity=FindingSeverity.MEDIUM,
        highlighted_text="NimbusDB",
        text_span=TextSpan(start=2, end=10),
        explanation="Prohibited variant",
        evidence_status=EvidenceStatus.VERIFIED,
    )
    assert finding.validate_against_text(full_text) is False


def test_review_input_valid():
    inp = ReviewInput(
        draft_id="d1",
        brand_id="b1",
        content_text="Sample text",
        visual_metadata=VisualMetadata(contrast_ratio=4.8, is_large_text=False),
    )
    assert inp.draft_id == "d1"
    assert inp.visual_metadata is not None
    assert inp.visual_metadata.contrast_ratio == 4.8


def test_decision_outcome_enums():
    outcome = DecisionOutcome(
        status=ReviewDecision.GREEN,
        action_required_by=ActionRequiredBy.NONE,
        reason="Clean draft",
    )
    assert outcome.status == ReviewDecision.GREEN
    assert outcome.action_required_by == ActionRequiredBy.NONE


def test_brand_policy_schema(nimbus_policy: BrandPolicy):
    assert nimbus_policy.brand_id == "nimbus_cloud"
    assert len(nimbus_policy.approved_terminology) > 0
    assert nimbus_policy.approved_terminology[0].approved_term == "Nimbus DB"
    assert "NimbusDB" in nimbus_policy.approved_terminology[0].prohibited_variants
