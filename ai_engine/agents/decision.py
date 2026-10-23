"""Decision Agent.

Stage 4 of the brand governance review pipeline.
Evaluates aggregated findings against strict decision precedence:
RED > YELLOW > GREEN.
Enforces strict mode guardrails and action assignment.
"""

from typing import List, Optional
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
)
from ai_engine.schemas.review import (
    ActionRequiredBy,
    DecisionOutcome,
    ReviewDecision,
)


def route_decision(findings: List[Finding], strict_mode: bool = False) -> DecisionOutcome:
    """Compute overall decision based on finding severities and evidence states.

    Decision Precedence: RED > YELLOW > GREEN.
    """
    if not findings:
        return DecisionOutcome(
            status=ReviewDecision.GREEN,
            action_required_by=ActionRequiredBy.NONE,
            clarification_question=None,
            reason="All deterministic and specialist brand governance checks passed.",
        )

    # Check for RED conditions
    has_critical = any(f.severity == FindingSeverity.CRITICAL for f in findings)
    has_contradicted = any(f.evidence_status == EvidenceStatus.CONTRADICTED for f in findings)
    has_high = any(f.severity == FindingSeverity.HIGH for f in findings)
    has_unsupported_without_evidence = any(
        (f.category == FindingCategory.UNSUPPORTED_CLAIM and f.evidence_status == EvidenceStatus.UNSUPPORTED)
        or (f.category == FindingCategory.LEGAL and f.severity in (FindingSeverity.HIGH, FindingSeverity.CRITICAL))
        for f in findings
    )

    # 1. RED Condition: Contradictions, retired offers, legal violations, critical/high findings, or unsupported claims (without user-supplied evidence)
    if has_critical or has_contradicted or has_high or has_unsupported_without_evidence:
        reasons = []
        if has_contradicted:
            reasons.append("contradicts authoritative brand facts or retired offers")
        if has_critical or has_high:
            reasons.append("contains high-risk policy violations or legal constraints")
        if has_unsupported_without_evidence and not (has_critical or has_high or has_contradicted):
            reasons.append("contains unsupported superlatives or claims without required benchmark")

        return DecisionOutcome(
            status=ReviewDecision.RED,
            action_required_by=ActionRequiredBy.REVIEWER_APPROVAL,
            clarification_question=None,
            reason=f"Review rejected: Draft {', '.join(reasons)}.",
        )

    # 2. YELLOW Condition: Ambiguity, unverified supplied evidence, tone mismatch, or medium findings under strict mode
    has_unverified = any(f.evidence_status == EvidenceStatus.UNVERIFIED_PROVIDED for f in findings)
    has_medium = any(f.severity == FindingSeverity.MEDIUM for f in findings)
    has_tone_mismatch = any(f.category == FindingCategory.TONE_MISMATCH for f in findings)

    if has_unverified or (has_medium and strict_mode) or has_tone_mismatch:
        question = None
        for f in findings:
            if f.evidence_status == EvidenceStatus.UNVERIFIED_PROVIDED:
                question = f"Can you provide verified source documentation for '{f.highlighted_text}'?"
                break
            if f.category == FindingCategory.TONE_MISMATCH:
                question = f"Can you rephrase '{f.highlighted_text}' to align with brand tone guidelines?"
                break
        if not question and strict_mode:
            question = "Please confirm the highlighted brand corrections before publishing."

        return DecisionOutcome(
            status=ReviewDecision.YELLOW,
            action_required_by=ActionRequiredBy.CREATOR_QUESTION,
            clarification_question=question,
            reason="Review pending: Draft contains unverified evidence or requires author clarification.",
        )

    # 3. GREEN with minor corrections (e.g. terminology with suggested fix)
    has_low_or_fixable_medium = all(
        f.severity in (FindingSeverity.LOW, FindingSeverity.MEDIUM) and f.suggested_fix
        for f in findings
    )

    if has_low_or_fixable_medium and not strict_mode:
        return DecisionOutcome(
            status=ReviewDecision.GREEN,
            action_required_by=ActionRequiredBy.CREATOR_ONE_CLICK,
            clarification_question=None,
            reason="Approved with recommendations: Apply one-click corrections for terminology or formatting.",
        )

    # Strict mode fallback for remaining non-clean drafts
    if strict_mode:
        return DecisionOutcome(
            status=ReviewDecision.YELLOW,
            action_required_by=ActionRequiredBy.CREATOR_QUESTION,
            clarification_question="Strict mode rejection: All highlighted brand findings must be reviewed.",
            reason="Draft rejected under strict mode policy: Manual confirmation required.",
        )

    return DecisionOutcome(
        status=ReviewDecision.YELLOW,
        action_required_by=ActionRequiredBy.CREATOR_ONE_CLICK,
        clarification_question=None,
        reason="Action required: Correct highlighted findings prior to release.",
    )


class DecisionAgent:
    """Agent implementing Stage 4 review decision logic."""

    def __init__(self, strict_mode: bool = False) -> None:
        self.strict_mode = strict_mode

    def evaluate(self, findings: List[Finding]) -> DecisionOutcome:
        """Evaluate aggregated findings and return validated DecisionOutcome."""
        return route_decision(findings, strict_mode=self.strict_mode)
