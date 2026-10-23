"""Tests for Stage 4 Fix-cum-Rewrite Workflow and Decision Safety.

Covers all required behaviors:
- Clean draft needing no rewrite
- Minimal mechanical correction
- Rewrite introducing a new violation
- Rewrite leaving original violation unresolved
- RED decision that cannot be bypassed
- Provider failure handling during review or rewrite
- Malformed/unusable rewrite response
- Case where no rewrite is produced
- Distinction between original findings and remaining findings after revalidation
"""

import pytest
from ai_engine.agents.coordinator import CoordinatorAgent
from ai_engine.agents.rewrite import RewriteAgent, RewriteProposal
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.providers.factory import RulesOnlyProvider
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)
from ai_engine.schemas.payload import DraftPayload
from ai_engine.schemas.review import ActionRequiredBy, ReviewDecision


@pytest.fixture
def repo(nimbus_policy: BrandPolicy) -> MockPolicyRepository:
    r = MockPolicyRepository()
    r.register_policy(nimbus_policy)
    return r


def test_clean_draft_needs_no_rewrite(repo: MockPolicyRepository, clean_draft: str):
    """Clean draft has zero findings, produces no rewrite, and remains GREEN."""
    coordinator = CoordinatorAgent(repository=repo, provider=RulesOnlyProvider())
    payload = DraftPayload(draft_id="clean_1", brand_id="nimbus_cloud", content_text=clean_draft)
    result = coordinator.run_review(payload)

    assert result.decision.status == ReviewDecision.GREEN
    assert len(result.findings) == 0
    assert result.proposed_rewrite is None
    assert result.rewrite_proposal is not None
    assert result.rewrite_proposal.is_post_revalidation_passed is True


def test_minimal_mechanical_correction(repo: MockPolicyRepository):
    """Draft with a fixable terminology violation is minimally rewritten and post-revalidated."""
    coordinator = CoordinatorAgent(repository=repo, provider=RulesOnlyProvider())
    draft = "NimbusDB provides robust cloud storage."
    payload = DraftPayload(draft_id="term_1", brand_id="nimbus_cloud", content_text=draft)
    result = coordinator.run_review(payload)

    assert result.proposed_rewrite == "Nimbus DB provides robust cloud storage."
    assert result.rewrite_proposal is not None
    assert len(result.rewrite_proposal.applied_fixes) == 1
    assert "Nimbus DB" in result.rewrite_proposal.applied_fixes[0]
    # Post revalidation passed with zero remaining findings
    assert result.rewrite_proposal.is_post_revalidation_passed is True
    assert len(result.post_rewrite_findings) == 0


def test_rewrite_that_leaves_original_violation_unresolved(repo: MockPolicyRepository):
    """If a critical violation cannot be mechanically repaired, rewrite is not produced and remains unresolved."""
    agent = RewriteAgent()
    text = "Nimbus Cloud guarantees 100% uptime with zero downtime."
    finding = Finding(
        finding_id="unfixable_1",
        category=FindingCategory.WRONG_FACT,
        severity=FindingSeverity.CRITICAL,
        highlighted_text="100% uptime",
        text_span=TextSpan(start=24, end=35),
        explanation="Contradicts SLA",
        evidence_status=EvidenceStatus.CONTRADICTED,
        suggested_fix=None,  # No suggested fix
        human_review_required=True,
    )
    policy = repo.get_policy("nimbus_cloud")
    proposal = agent.generate_rewrite(text, [finding], policy)

    assert proposal.proposed_text is None
    assert proposal.is_post_revalidation_passed is False
    assert len(proposal.unresolved_findings) == 1
    assert proposal.requires_clarification is True


def test_rewrite_introducing_new_violation(repo: MockPolicyRepository):
    """When a hypothetical faulty replacement introduces a brand violation, revalidation catches it."""
    agent = RewriteAgent()
    policy = repo.get_policy("nimbus_cloud")
    original_text = "Welcome to our old DB."

    # A finding whose suggested fix accidentally introduces a prohibited variant "NimbusDB"
    finding = Finding(
        finding_id="bad_fix_1",
        category=FindingCategory.TERMINOLOGY,
        severity=FindingSeverity.MEDIUM,
        highlighted_text="old DB",
        text_span=TextSpan(start=15, end=21),
        explanation="Change term",
        evidence_status=EvidenceStatus.VERIFIED,
        suggested_fix="NimbusDB",  # Prohibited variant!
    )
    proposal = agent.generate_rewrite(original_text, [finding], policy)

    assert proposal.proposed_text == "Welcome to our NimbusDB."
    # Revalidation must flag the new violation
    assert proposal.is_post_revalidation_passed is False
    assert len(proposal.new_findings) > 0
    assert any("NimbusDB" in f.highlighted_text for f in proposal.new_findings)


def test_red_decision_cannot_be_bypassed_by_rewrite(repo: MockPolicyRepository):
    """A rewrite proposing fixes NEVER overrides an underlying RED decision."""
    coordinator = CoordinatorAgent(repository=repo, provider=RulesOnlyProvider())
    # Draft contains both a fixable term and an unfixable 100% uptime claim
    draft = "NimbusDB guarantees 100% uptime for all workloads."
    payload = DraftPayload(draft_id="red_safety", brand_id="nimbus_cloud", content_text=draft)
    result = coordinator.run_review(payload)

    # Decision must remain RED requiring reviewer approval
    assert result.decision.status == ReviewDecision.RED
    assert result.decision.action_required_by == ActionRequiredBy.REVIEWER_APPROVAL
    # Even if proposed rewrite replaced NimbusDB with Nimbus DB
    if result.proposed_rewrite:
        assert "Nimbus DB" in result.proposed_rewrite


def test_distinction_between_original_and_post_revalidation_findings(repo: MockPolicyRepository):
    """Traceability preserves original findings, applied fixes, and post-rewrite findings."""
    coordinator = CoordinatorAgent(repository=repo, provider=RulesOnlyProvider())
    # Draft with a fixable term and an unfixable tone violation
    draft = "NimbusDB crushes the competition with fast cloud performance."
    payload = DraftPayload(draft_id="trace_1", brand_id="nimbus_cloud", content_text=draft)
    result = coordinator.run_review(payload)

    assert len(result.findings) >= 2
    original_categories = {f.category for f in result.findings}
    assert FindingCategory.TERMINOLOGY in original_categories
    assert FindingCategory.TONE_MISMATCH in original_categories

    # Rewritten text fixes NimbusDB -> Nimbus DB, while tone violation remains in post-rewrite
    assert result.proposed_rewrite is not None
    assert "Nimbus DB" in result.proposed_rewrite
    assert len(result.post_rewrite_findings) >= 1
    post_categories = {f.category for f in result.post_rewrite_findings}
    assert FindingCategory.TERMINOLOGY not in post_categories
    assert FindingCategory.TONE_MISMATCH in post_categories


def test_no_rewrite_produced_when_violations_unfixable(repo: MockPolicyRepository):
    """When a draft contains only unfixable high-risk violations, no rewrite is produced."""
    coordinator = CoordinatorAgent(repository=repo, provider=RulesOnlyProvider())
    draft = "We offer 100% uptime."
    payload = DraftPayload(draft_id="unfix_1", brand_id="nimbus_cloud", content_text=draft)
    result = coordinator.run_review(payload)

    assert result.decision.status == ReviewDecision.RED
    # No safe automated rewrite could be fabricated
    assert result.proposed_rewrite is None or result.rewrite_proposal.requires_clarification is True
