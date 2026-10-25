"""The brand manager's own DO and DON'T rules are enforced, not just displayed."""

import pytest

from ai_engine.agents.coordinator import CoordinatorAgent
from ai_engine.agents.specialists.guideline_specialist import (
    GuidelineSpecialist,
    banned_terms,
    guideline_prompt,
    parse_guideline_verdicts,
)
from ai_engine.config import EngineConfig
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.providers.factory import RulesOnlyProvider
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.payload import DraftPayload, WorkspaceRule

TOPIC = "Nothing should be out of topic like gaming, government work etc all should be about fitness, gym etc"
LENGTH = "No short reports or contents should be submitted all should be detailed"


@pytest.fixture
def repo():
    r = MockPolicyRepository()
    r.load_fixture("data/brand_library/nimbus_db.json")
    return r


def payload(text, *rules):
    return DraftPayload(draft_id="g", brand_id="nimbus_cloud", content_text=text,
                        workspace_rules=[WorkspaceRule(type=t, text=r) for t, r in rules])


def policy(repo) -> BrandPolicy:
    return repo.get_policy("nimbus_cloud")


@pytest.mark.parametrize("rule,expected", [
    ("Never use the word cheap.", ["cheap"]),
    ('Do not say "best ever" or "guaranteed"', ["best ever", "guaranteed"]),
    ("Avoid cheap, free or guaranteed", ["cheap", "free", "guaranteed"]),
    ("Don't mention competitors", ["competitors"]),
    (LENGTH, []),
    (TOPIC, []),
    ("Ojas is a fitness company", []),
])
def test_only_clear_word_bans_are_read_as_word_bans(rule, expected):
    assert banned_terms(rule) == expected


def test_a_banned_word_is_a_firm_finding_with_the_quote():
    out = GuidelineSpecialist().evaluate(payload("Our gym is cheap and great.", ("DON'T", "Never use the word cheap.")), None)
    assert len(out) == 1
    f = out[0]
    assert (f.category.value, f.severity.value, f.highlighted_text) == ("brand_guideline", "high", "cheap")
    assert "Never use the word cheap" in f.cited_source and f.human_review_required


def test_a_followed_word_ban_produces_nothing():
    assert GuidelineSpecialist().evaluate(payload("Our gym is great value.", ("DON'T", "Never use the word cheap.")), None) == []


def test_word_bans_match_whole_words_only():
    assert GuidelineSpecialist().evaluate(payload("Cheaper than ever? No: cheapest is not a promise.", ("DON'T", "Never use the word cheap.")), None) == []


def test_rules_that_cannot_be_checked_are_reported_not_assumed_followed():
    out = GuidelineSpecialist(RulesOnlyProvider()).evaluate(payload("Gaming is fun.", ("DON'T", TOPIC), ("DO", "Ojas is a fitness company")), None)
    assert len(out) == 1
    f = out[0]
    assert f.severity.value == "medium" and f.human_review_required
    assert "2 workspace rule(s)" in f.explanation and "fitness" in f.explanation


class Judge:
    provider_name = "fake"

    def __init__(self, verdicts=None, boom=False):
        self.verdicts, self.boom, self.asked = verdicts or {}, boom, None

    def check_guidelines(self, text, rules):
        self.asked = rules
        if self.boom:
            raise RuntimeError("down")
        return self.verdicts


def test_a_model_violation_is_advisory_and_quoted():
    j = Judge({1: {"verdict": "violated", "quote": "Gaming is fun", "reason": "This is about gaming, not fitness."}})
    out = GuidelineSpecialist(j).evaluate(payload("Gaming is fun. Join us.", ("DON'T", TOPIC)), None)
    assert len(out) == 1 and out[0].severity.value == "medium" and out[0].human_review_required
    assert out[0].highlighted_text == "Gaming is fun" and "not fitness" in out[0].explanation
    assert j.asked == [("DON'T", TOPIC)]


def test_a_model_violation_without_a_quote_points_at_the_start_of_the_draft():
    j = Judge({1: {"verdict": "violated", "quote": "words that are not there", "reason": "Off topic."}})
    out = GuidelineSpecialist(j).evaluate(payload("Gaming is fun.", ("DON'T", TOPIC)), None)
    assert out[0].text_span.start == 0 and out[0].highlighted_text == "Gaming is fun."


def test_a_complying_verdict_clears_that_rule_only():
    j = Judge({1: {"verdict": "complies"}})
    assert GuidelineSpecialist(j).evaluate(payload("Leg day tips for the gym.", ("DO", "Be about fitness"), ), None) == []
    j = Judge({1: {"verdict": "complies"}})  # rule 2 is not answered: it stays unchecked
    out = GuidelineSpecialist(j).evaluate(payload("Leg day.", ("DO", "Be about fitness"), ("DON'T", LENGTH)), None)
    assert len(out) == 1 and "1 workspace rule(s)" in out[0].explanation and "detailed" in out[0].explanation


@pytest.mark.parametrize("judge", [Judge({1: {"verdict": "unclear"}}), Judge({}), Judge(boom=True), Judge({1: {"verdict": "maybe"}})])
def test_unclear_missing_or_failed_model_answers_stay_unchecked(judge):
    out = GuidelineSpecialist(judge).evaluate(payload("Leg day.", ("DO", "Be about fitness")), None)
    assert len(out) == 1 and "could not check" in out[0].explanation


def test_mechanical_rules_never_reach_the_model():
    j = Judge({})
    GuidelineSpecialist(j).evaluate(payload("Hello.", ("DON'T", "Never use the word cheap.")), None)
    assert j.asked is None


def test_no_rules_or_no_text_means_no_findings():
    assert GuidelineSpecialist().evaluate(payload("Hello."), None) == []
    assert GuidelineSpecialist().evaluate(payload("", ("DON'T", "Never use the word cheap.")), None) == []


def test_verdict_parsing_is_forgiving_but_never_invents_answers():
    raw = 'noise {"results":[{"rule":1,"verdict":"VIOLATED","quote":"x","reason":"r"},{"rule":"bad"},{"verdict":"complies"}]} tail'
    assert parse_guideline_verdicts(raw) == {1: {"verdict": "violated", "quote": "x", "reason": "r"}}
    assert parse_guideline_verdicts("not json") == {}
    assert "=== DRAFT ===" in guideline_prompt("hi", [("DO", "x")]) and "untrusted" in guideline_prompt("hi", [("DO", "x")])


def run(repo, text, *rules, provider=None):
    agent = CoordinatorAgent(repo, config=EngineConfig(), provider=provider or RulesOnlyProvider(), retriever=None)
    return agent.run_review(payload(text, *rules))


def test_a_banned_word_makes_the_whole_review_red(repo):
    result = run(repo, "Nimbus DB is a cheap platform for modern teams.", ("DON'T", "Never use the word cheap."))
    assert result.decision.status.value == "RED"
    assert any(f.category.value == "brand_guideline" and f.highlighted_text == "cheap" for f in result.findings)


def test_an_unchecked_rule_stops_a_clean_draft_being_ready(repo):
    clean = "Nimbus DB is a reliable platform for modern teams."
    assert run(repo, clean).decision.status.value == "GREEN"
    result = run(repo, clean, ("DO", "Ojas is a fitness company"))
    assert result.decision.status.value != "GREEN"
    assert any(f.human_review_required and f.category.value == "brand_guideline" for f in result.findings)
