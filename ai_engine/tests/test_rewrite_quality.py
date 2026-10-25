"""Rewrites must stay grammatical and must not hide unresolved violations."""

import pytest

from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.review import run_brand_review
from ai_engine.schemas.review import ReviewInput

FIXTURE = "data/brand_library/nimbus_db.json"


@pytest.fixture
def review(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    repo = MockPolicyRepository()
    repo.load_fixture(FIXTURE)
    return lambda text: run_brand_review(
        ReviewInput(draft_id="t", brand_id="nimbus_cloud", content_text=text), repository=repo
    )


def test_excess_exclamation_marks_are_collapsed(review):
    result = review("Nimbus DB is a reliable platform for modern teams!!")
    assert result.proposed_rewrite == "Nimbus DB is a reliable platform for modern teams!"


def test_retired_offer_is_not_spliced_into_the_sentence(review):
    result = review("Try it free forever and see why teams love it.")
    assert "14-day free trial" not in (result.proposed_rewrite or "")
    assert any(f.category.value == "outdated_offer" for f in result.post_rewrite_findings)


def test_rewrite_never_clears_a_red_decision(review):
    result = review("NimbusDB has 100% uptime. Try it free forever.")
    assert result.decision.status.value == "RED"
    assert result.post_rewrite_findings


def test_sla_claim_without_disclaimer_gets_one_click_disclaimer(review):
    result = review("Nimbus DB keeps your data safe with a 99.95% uptime SLA.")
    assert result.decision.status.value == "GREEN"
    assert result.decision.action_required_by.value == "creator_one_click"
    assert result.proposed_rewrite == (
        "Nimbus DB keeps your data safe with a 99.95% uptime SLA. Terms and conditions apply to service SLA."
    )
    assert not result.post_rewrite_findings


def test_sla_claim_with_disclaimer_is_clean(review):
    result = review("Nimbus DB has a 99.95% uptime SLA. Terms and conditions apply to service SLA.")
    assert result.decision.status.value == "GREEN" and not result.findings


def test_absolute_sla_promise_is_still_red_and_rewrite_keeps_the_draft(review):
    result = review("Nimbus DB has a guaranteed SLA.")
    assert result.decision.status.value == "RED"
    assert (result.proposed_rewrite or "").startswith("Nimbus DB has a guaranteed SLA")


def test_data_driven_tone_phrases_and_restricted_claims(review):
    result = review("Act now! Nimbus DB is fully compliant, just trust us.")
    texts = {f.highlighted_text.lower() for f in result.findings}
    assert {"act now", "just trust us", "fully compliant"} <= texts
