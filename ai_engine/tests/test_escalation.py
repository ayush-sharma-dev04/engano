"""Human-reviewer escalation: when the engine is not sure, a person decides."""

import pytest

from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.review import run_brand_review
from ai_engine.schemas.review import ReviewInput
from engano_backend.escalation import (
    EscalationSettings,
    escalation_for,
    normalize_whatsapp_number,
    reviewer_message,
)


@pytest.fixture
def review(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    repo = MockPolicyRepository()
    repo.load_fixture("data/brand_library/nimbus_db.json")
    return lambda text, brand="nimbus_cloud": run_brand_review(
        ReviewInput(draft_id="d1", brand_id=brand, content_text=text), repository=repo
    )


@pytest.mark.parametrize("raw,expected", [
    ("9876500001", "919876500001"),
    ("+91 98765 00001", "919876500001"),
    ("919876500001", "919876500001"),
    ("", None),
    (None, None),
])
def test_number_normalisation(raw, expected):
    assert normalize_whatsapp_number(raw) == expected


def test_settings_read_from_env(monkeypatch):
    monkeypatch.setenv("ENGANO_REVIEWER_WHATSAPP", "9876500001")
    monkeypatch.setenv("ENGANO_REVIEWER_DISCORD_ID", "100000000000000001")
    s = EscalationSettings.from_env()
    assert s.whatsapp_number == "919876500001" and s.discord_user_id == 100000000000000001
    monkeypatch.delenv("ENGANO_REVIEWER_WHATSAPP")
    monkeypatch.delenv("ENGANO_REVIEWER_DISCORD_ID")
    assert EscalationSettings.from_env() == EscalationSettings()


def test_clean_draft_is_not_escalated(review):
    needed, reasons = escalation_for(review("Nimbus DB is a reliable platform for modern teams."))
    assert not needed and reasons == []


def test_red_draft_is_escalated(review):
    needed, reasons = escalation_for(review("NimbusDB has 100% uptime."))
    assert needed and any("reviewer approval" in r for r in reasons)


def test_failed_review_is_escalated(review):
    result = review("hello", brand="unknown_brand")
    needed, reasons = escalation_for(result)
    assert needed and any("did not complete" in r for r in reasons)


def test_message_has_everything_the_reviewer_needs(review):
    draft = "NimbusDB has 100% uptime."
    result = review(draft)
    _, reasons = escalation_for(result)
    text = reviewer_message(result, draft, "WhatsApp", "+919800000000", reasons)
    for part in ("needs your review", "WhatsApp", "+919800000000", "nimbus_cloud", "RED", draft, "100% uptime", "Ref: d1"):
        assert part in text
