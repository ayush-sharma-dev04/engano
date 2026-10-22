"""Tests for AI agent components."""

from ai_engine.agents.evidence_validation import EvidenceValidationAgent
from ai_engine.agents.governance import GovernanceAgent
from ai_engine.agents.policy_analysis import PolicyAnalysisAgent
from ai_engine.agents.rewrite import RewriteAgent
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)


def test_policy_analysis_agent_scope(nimbus_policy: BrandPolicy):
    agent = PolicyAnalysisAgent()
    draft = "NimbusDB claims 100% uptime and free forever access."
    scope = agent.analyze_scope(draft, nimbus_policy)
    assert scope.brand_id == "nimbus_cloud"
    assert "terminology" in scope.applicable_topics
    assert "uptime_sla" in scope.applicable_topics
    assert "promotional_offers" in scope.applicable_topics
    assert scope.requires_uptime_check is True


def test_evidence_validation_agent_classification(nimbus_policy: BrandPolicy):
    agent = EvidenceValidationAgent()
    finding_unsupported = Finding(
        finding_id="f1",
        category=FindingCategory.UNSUPPORTED_CLAIM,
        severity=FindingSeverity.HIGH,
        highlighted_text="fastest database",
        text_span=TextSpan(start=0, end=16),
        explanation="Needs benchmark",
        evidence_status=EvidenceStatus.UNSUPPORTED,
    )
    # Without supplied evidence, remains unsupported
    res = agent.validate_findings([finding_unsupported], nimbus_policy, supplied_evidence=None)
    assert res[0].evidence_status == EvidenceStatus.UNSUPPORTED

    # With user-supplied evidence, marked as unverified_provided
    res_with_ev = agent.validate_findings(
        [finding_unsupported],
        nimbus_policy,
        supplied_evidence="We tested the fastest database on our internal servers",
    )
    assert res_with_ev[0].evidence_status == EvidenceStatus.UNVERIFIED_PROVIDED


def test_rewrite_agent_safe_correction(nimbus_policy: BrandPolicy):
    agent = RewriteAgent()
    text = "Use NimbusDB for your database."
    finding = Finding(
        finding_id="term_1",
        category=FindingCategory.TERMINOLOGY,
        severity=FindingSeverity.MEDIUM,
        highlighted_text="NimbusDB",
        text_span=TextSpan(start=4, end=12),
        explanation="Use approved term",
        evidence_status=EvidenceStatus.VERIFIED,
        suggested_fix="Nimbus DB",
    )
    proposal = agent.generate_rewrite(text, [finding], nimbus_policy)
    assert proposal.proposed_text == "Use Nimbus DB for your database."
    assert len(proposal.applied_fixes) == 1
    assert proposal.requires_clarification is False


def test_rewrite_agent_does_not_fabricate_claims(nimbus_policy: BrandPolicy):
    agent = RewriteAgent()
    text = "NimbusDB has 100% uptime."
    findings = [
        Finding(
            finding_id="term_1",
            category=FindingCategory.TERMINOLOGY,
            severity=FindingSeverity.MEDIUM,
            highlighted_text="NimbusDB",
            text_span=TextSpan(start=0, end=8),
            explanation="Spelling",
            evidence_status=EvidenceStatus.VERIFIED,
            suggested_fix="Nimbus DB",
        ),
        Finding(
            finding_id="fact_1",
            category=FindingCategory.WRONG_FACT,
            severity=FindingSeverity.CRITICAL,
            highlighted_text="100% uptime",
            text_span=TextSpan(start=13, end=24),
            explanation="Contradiction",
            evidence_status=EvidenceStatus.CONTRADICTED,
            suggested_fix="99.95% uptime SLA",
        ),
    ]
    proposal = agent.generate_rewrite(text, findings, nimbus_policy)
    # Preserves sentence structure and replaces with policy fix without adding extra hype
    assert proposal.proposed_text == "Nimbus DB has 99.95% uptime SLA."
    assert "best" not in proposal.proposed_text.lower()
    assert "guaranteed" not in proposal.proposed_text.lower()


def test_governance_agent_advisory_only(nimbus_policy: BrandPolicy):
    agent = GovernanceAgent()
    findings = [
        Finding(
            finding_id="f1",
            category=FindingCategory.TERMINOLOGY,
            severity=FindingSeverity.MEDIUM,
            highlighted_text="NimbusDB",
            text_span=TextSpan(start=0, end=8),
            explanation="Spelling",
            evidence_status=EvidenceStatus.VERIFIED,
        ),
        Finding(
            finding_id="f2",
            category=FindingCategory.TERMINOLOGY,
            severity=FindingSeverity.MEDIUM,
            highlighted_text="Nimbus-DB",
            text_span=TextSpan(start=10, end=19),
            explanation="Spelling",
            evidence_status=EvidenceStatus.VERIFIED,
        ),
    ]
    report = agent.analyze_review_outcomes(findings, historical_overrides=None)
    assert report.total_findings_analyzed == 2
    assert "terminology" in report.recurring_gap_categories
    assert len(report.recommendations) > 0
    # Every recommendation requires human approval and never mutates policy
    for rec in report.recommendations:
        assert rec.requires_human_approval is True
    assert report.has_historical_override_data is False
    assert report.data_limitation_notice is not None
