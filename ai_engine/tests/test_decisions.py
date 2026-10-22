"""Tests for decision routing, precedence, and strict mode."""

from ai_engine.agents.orchestrator import _route_decision
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)
from ai_engine.schemas.review import ActionRequiredBy, ReviewDecision


def test_green_decision_empty_findings():
    decision = _route_decision([], strict_mode=False)
    assert decision.status == ReviewDecision.GREEN
    assert decision.action_required_by == ActionRequiredBy.NONE


def test_green_with_minor_one_click_correction():
    minor_finding = Finding(
        finding_id="f1",
        category=FindingCategory.TERMINOLOGY,
        severity=FindingSeverity.LOW,
        highlighted_text="NimbusDB",
        text_span=TextSpan(start=0, end=8),
        explanation="Use approved term",
        evidence_status=EvidenceStatus.VERIFIED,
        suggested_fix="Nimbus DB",
    )
    decision = _route_decision([minor_finding], strict_mode=False)
    assert decision.status == ReviewDecision.GREEN
    assert decision.action_required_by == ActionRequiredBy.CREATOR_ONE_CLICK_CORRECTION


def test_yellow_decision_unverified_evidence():
    unverified_finding = Finding(
        finding_id="f2",
        category=FindingCategory.UNSUPPORTED_CLAIM,
        severity=FindingSeverity.LOW,
        highlighted_text="Fastest database in the world",
        text_span=TextSpan(start=0, end=29),
        explanation="Evidence supplied by user needs verification",
        evidence_status=EvidenceStatus.UNVERIFIED_PROVIDED,
    )
    decision = _route_decision([unverified_finding], strict_mode=False)
    assert decision.status == ReviewDecision.YELLOW
    assert decision.action_required_by == ActionRequiredBy.CREATOR_CLARIFICATION
    assert decision.clarification_question is not None


def test_red_precedence_over_yellow_and_green():
    # Combining a minor term fix, unverified evidence, and a critical contradiction
    f_green = Finding(
        finding_id="f1",
        category=FindingCategory.TERMINOLOGY,
        severity=FindingSeverity.LOW,
        highlighted_text="NimbusDB",
        text_span=TextSpan(start=0, end=8),
        explanation="Minor spelling",
        evidence_status=EvidenceStatus.VERIFIED,
        suggested_fix="Nimbus DB",
    )
    f_yellow = Finding(
        finding_id="f2",
        category=FindingCategory.UNSUPPORTED_CLAIM,
        severity=FindingSeverity.LOW,
        highlighted_text="fastest",
        text_span=TextSpan(start=10, end=17),
        explanation="Unverified",
        evidence_status=EvidenceStatus.UNVERIFIED_PROVIDED,
    )
    f_red = Finding(
        finding_id="f3",
        category=FindingCategory.WRONG_FACT,
        severity=FindingSeverity.CRITICAL,
        highlighted_text="100% uptime",
        text_span=TextSpan(start=20, end=31),
        explanation="Direct contradiction with 99.95% SLA",
        evidence_status=EvidenceStatus.CONTRADICTED,
    )

    decision = _route_decision([f_green, f_yellow, f_red], strict_mode=False)
    assert decision.status == ReviewDecision.RED
    assert decision.action_required_by == ActionRequiredBy.REVIEWER_APPROVAL


def test_strict_mode_escalation():
    medium_finding = Finding(
        finding_id="f1",
        category=FindingCategory.TERMINOLOGY,
        severity=FindingSeverity.MEDIUM,
        highlighted_text="NimbusDB",
        text_span=TextSpan(start=0, end=8),
        explanation="Spelling issue",
        evidence_status=EvidenceStatus.VERIFIED,
        suggested_fix="Nimbus DB",
    )
    # Under standard mode, fixable medium can be GREEN with one-click fix
    dec_standard = _route_decision([medium_finding], strict_mode=False)
    assert dec_standard.status == ReviewDecision.GREEN

    # Under strict mode, medium severity enforces YELLOW clarification
    dec_strict = _route_decision([medium_finding], strict_mode=True)
    assert dec_strict.status == ReviewDecision.YELLOW
    assert dec_strict.action_required_by == ActionRequiredBy.CREATOR_CLARIFICATION
