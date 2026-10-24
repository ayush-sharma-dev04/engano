"""ENGANO asks for more information instead of guessing."""

import pytest

from ai_engine.agents.coordinator import CoordinatorAgent
from ai_engine.agents.questions import evidence_question_id
from ai_engine.config import EngineConfig
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.providers.factory import RulesOnlyProvider
from ai_engine.schemas.payload import DraftPayload

LONG_OFF_BRAND = (
    "Tired of laggy Minecraft servers and unexpected crashes? Welcome to BlockHost, where your adventures "
    "deserve better. We provide reliable hosting designed for everyone, from small survival groups to massive "
    "multiplayer communities, with easy management and room to grow as your world gets bigger every single day."
)
SUPERLATIVE = "Nimbus DB is the fastest database in the world."


@pytest.fixture
def agent():
    repo = MockPolicyRepository()
    repo.load_fixture("data/brand_library/nimbus_db.json")
    return CoordinatorAgent(repo, config=EngineConfig(), provider=RulesOnlyProvider(), retriever=None)


def run(agent, text, **kw):
    return agent.run_review(DraftPayload(draft_id="q", brand_id="nimbus_cloud", content_text=text, **kw))


def test_long_draft_that_never_mentions_the_brand_is_not_ready_to_publish(agent):
    result = run(agent, LONG_OFF_BRAND)
    assert result.decision.status.value == "YELLOW"
    assert result.decision.action_required_by.value == "creator_question"
    q = result.questions[0]
    assert q.id == "brand" and q.kind == "confirm_brand" and len(q.choices) == 2 and "Nimbus Cloud" in q.text
    assert result.decision.clarification_question == q.text


def test_short_or_on_brand_drafts_are_not_questioned(agent):
    assert run(agent, "Hello there.").questions == []
    assert run(agent, "Nimbus DB is a reliable platform. " + "We help teams ship. " * 15).questions == []


def test_confirming_the_brand_clears_the_question(agent):
    result = run(agent, LONG_OFF_BRAND, answers={"brand": "Yes, it's for Nimbus Cloud"})
    assert result.questions == [] and result.decision.status.value == "GREEN"


def test_saying_it_is_another_brand_sends_it_to_a_reviewer(agent):
    result = run(agent, LONG_OFF_BRAND, answers={"brand": "No, it's for another brand"})
    assert result.decision.status.value == "RED"
    assert any(f.cited_source == "Brand confirmation" for f in result.findings)


def test_unsupported_claim_asks_for_proof_and_for_the_website(agent):
    result = run(agent, SUPERLATIVE)
    kinds = {q.kind for q in result.questions}
    assert kinds == {"evidence", "website"}
    ev = next(q for q in result.questions if q.kind == "evidence")
    assert ev.id == evidence_question_id("fastest database in the world") and ev.about


def test_naming_the_permitted_benchmark_moves_the_claim_to_verification(agent):
    qid = evidence_question_id("fastest database in the world")
    result = run(agent, SUPERLATIVE, answers={qid: "Benchmark B-4"}, supplied_evidence=["Benchmark B-4"])
    claim = next(f for f in result.findings if f.category.value == "unsupported_claim")
    assert claim.evidence_status.value == "unverified_provided" and claim.severity.value == "low"
    assert not [q for q in result.questions if q.kind == "evidence"]
    assert result.decision.status.value == "YELLOW"  # a person still verifies the benchmark


def test_answered_questions_are_not_asked_again(agent):
    qid = evidence_question_id("fastest database in the world")
    result = run(agent, SUPERLATIVE, answers={qid: "see our blog", "website": "example.com"})
    assert result.questions == []


def test_website_that_repeats_the_claim_adds_context_but_never_clears_it(agent):
    result = run(
        agent, SUPERLATIVE, answers={"website": "https://example.com"},
        website_url="https://example.com/", website_text="Nimbus DB is the fastest database in the world!",
    )
    f = next(f for f in result.findings if f.category.value == "unsupported_claim")
    assert "appears on https://example.com/" in f.explanation and "independent evidence" in f.explanation
    assert result.decision.status.value == "RED"


def test_unreadable_website_is_asked_again_with_the_reason(agent):
    result = run(agent, SUPERLATIVE, answers={"website": "nope"}, website_error="that address doesn't exist")
    q = next(q for q in result.questions if q.kind == "website")
    assert "that address doesn't exist" in q.text


def test_questions_for_claims_in_images_are_clean_and_not_duplicated():
    from ai_engine.schemas.findings import EvidenceStatus, Finding, FindingCategory, FindingSeverity, TextSpan
    from ai_engine.agents.questions import QuestionAgent
    from ai_engine.schemas.payload import DraftPayload

    def claim(text):
        return Finding(finding_id=text, category=FindingCategory.UNSUPPORTED_CLAIM, severity=FindingSeverity.HIGH,
                       highlighted_text=text, text_span=TextSpan(start=0, end=0), explanation="e",
                       evidence_status=EvidenceStatus.UNSUPPORTED, human_review_required=True)

    repo = MockPolicyRepository()
    repo.load_fixture("data/brand_library/nimbus_db.json")
    policy = repo.get_policy("nimbus_cloud")
    findings = [claim("[Image 1] fastest database"), claim("[Image 1] fastest database in the world")]
    qs = [q for q in QuestionAgent().generate(DraftPayload(draft_id="d", brand_id="nimbus_cloud", content_text="x"), policy, findings)
          if q.kind == "evidence"]
    assert len(qs) == 1 and qs[0].about == "fastest database in the world" and "[Image" not in qs[0].text
