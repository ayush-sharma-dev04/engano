"""Brand-agnostic regression suites (Scenarios A-H).

Verifies that the review pipeline is driven by the draft supplied in the
current request and the explicitly resolved brand configuration. Nimbus
Cloud is treated strictly as a sample fixture: it must never be applied to
another brand's review, and test brands below are isolated fixtures that
never touch production data.
"""

import asyncio
import json
from pathlib import Path

import pytest

from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.memory.store import FileBrandMemoryStore
from ai_engine.review import run_brand_review
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.payload import DraftPayload
from ai_engine.schemas.review import ReviewDecision

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "test_brands"

OJAS_DRAFT = (
    "We're building OJAS, an AI-powered fitness platform with exercise tracking, "
    "competitive face-offs, and fitness challenges. We're looking for a creator to "
    "produce a promotional video explaining the product and our vision for combining "
    "AI, fitness, and competitive gaming. This is a paid collaboration, and the "
    "budget is negotiable."
)

BAKERY_VIOLATION_DRAFT = (
    "Crumb&Rye introduces its new seasonal bread range: stone-milled rye, honey "
    "oat sourdough, and wood-fired baguettes, baked fresh every morning. Preorder "
    "via our app."
)

BAKERY_CLEAN_DRAFT = (
    "Crumb & Rye introduces its new seasonal bread range: stone-milled rye, honey "
    "oat sourdough, and wood-fired baguettes, baked fresh every morning. Preorder "
    "via our app."
)

FINANCIAL_GUARANTEE_DRAFT = (
    "LedgerPro Accounting offers guaranteed investment returns for every"
    " subscriber, even in market downturns."
)

FINANCIAL_GUARANTEE_SHARED_TEXT = (
    "OJAS offers guaranteed investment returns for every subscriber."
)

FINANCIAL_CLEAN_DRAFT = (
    "LedgerPro Accounting syncs your bank feeds, generates monthly reports, and "
    "keeps your books audit-ready. Pricing starts at $19 per month."
)

FIVE_BRAND_FIXTURES = ("ojas_fitness", "crumb_and_rye_bakery", "ledgerpro_finance")


def _load_policy(name: str) -> BrandPolicy:
    data = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return BrandPolicy.model_validate(data)


def _repository_with(*brand_names: str, include_nimbus: bool = True) -> MockPolicyRepository:
    repo = MockPolicyRepository()
    for name in brand_names:
        repo.register_policy(_load_policy(name))
    if include_nimbus:
        nimbus_path = Path(__file__).resolve().parents[2] / "data" / "brand_library" / "nimbus_db.json"
        repo.register_policy(BrandPolicy.model_validate(json.loads(nimbus_path.read_text(encoding="utf-8"))))
    return repo


def _review(payload: DraftPayload, repo: MockPolicyRepository):
    return run_brand_review(
        payload,
        repository=repo,
        config=None,
        provider=None,
        brand_memory=None,
    )


def _payload(brand_id: str, content_text: str, draft_id: str = "d1") -> DraftPayload:
    return DraftPayload(draft_id=draft_id, brand_id=brand_id, content_text=content_text)


# ---------------------------------------------------------------- Scenario A
def test_scenario_a_ojas_draft_reviewed_against_ojas_policy():
    repo = _repository_with("ojas_fitness")
    result = _review(_payload("ojas_fitness", OJAS_DRAFT, "draft_ojas"), repo)

    assert result.completion_status == "completed"
    assert result.brand_id == "ojas_fitness"
    # A collaborator-opportunity draft contains no policy violations: no invented
    # medical claims, guaranteed results, or Nimbus findings.
    assert result.findings == []
    assert result.decision.status == ReviewDecision.GREEN
    assert result.proposed_rewrite is None
    # No Nimbus-specific suggestions were fabricated from the sample brand.
    assert "99.95" not in (result.proposed_rewrite or "")
    assert all("nimbus" not in f.explanation.lower() for f in result.findings)
    assert result.metadata.policy_source == "test_fixture"


# ---------------------------------------------------------------- Scenario B
def test_scenario_b_bakery_review_uses_only_bakery_policy():
    repo = _repository_with("crumb_and_rye_bakery")
    result = _review(_payload("crumb_and_rye_bakery", BAKERY_VIOLATION_DRAFT, "draft_bakery"), repo)

    assert result.completion_status == "completed"
    # The only finding is the bakery's own terminology violation; nothing from
    # Nimbus or OJAS appears.
    assert any(f.category.value == "terminology" for f in result.findings)
    assert all(f.highlighted_text == "Crumb&Rye" for f in result.findings)
    assert all("nimbus" not in f.explanation.lower() for f in result.findings)
    assert all("uptime" not in f.explanation.lower() for f in result.findings)


def test_scenario_b_clean_bakery_draft_gets_no_findings():
    repo = _repository_with("crumb_and_rye_bakery")
    result = _review(_payload("crumb_and_rye_bakery", BAKERY_CLEAN_DRAFT, "draft_bakery2"), repo)
    assert result.findings == []
    assert result.decision.status == ReviewDecision.GREEN


# ---------------------------------------------------------------- Scenario C
def test_scenario_c_financial_guarantee_flagged_only_under_financial_policy():
    repo = _repository_with("ledgerpro_finance")
    result = _review(_payload("ledgerpro_finance", FINANCIAL_GUARANTEE_DRAFT, "draft_fin"), repo)

    assert result.completion_status == "completed"
    contradiction = [f for f in result.findings if f.category.value == "wrong_fact"]
    assert contradiction, "Configured policy must flag the guaranteed-returns claim."
    finding = contradiction[0]
    assert finding.severity.value == "critical"
    assert finding.evidence_status.value == "contradicted"
    # Explanation derives from the brand's own factual rule, not Nimbus.
    assert "LedgerPro Accounting is bookkeeping" in finding.explanation
    assert "Nimbus" not in finding.explanation
    assert "100% uptime" not in finding.explanation


def test_scenario_c_financial_ordinary_product_copy_not_flagged():
    repo = _repository_with("ledgerpro_finance")
    result = _review(
        _payload("ledgerpro_finance", FINANCIAL_CLEAN_DRAFT, "draft_fin_clean"),
        repo,
    )
    assert result.findings == []
    assert result.decision.status == ReviewDecision.GREEN


def test_scenario_c_guarantee_text_not_flagged_under_unrelated_brands():
    """Same text, different brand: only LedgerPro's policy flags the guarantee."""
    repo = _repository_with("crumb_and_rye_bakery", "ojas_fitness")
    shared_text = FINANCIAL_GUARANTEE_SHARED_TEXT

    bakery_result = _review(_payload("crumb_and_rye_bakery", shared_text, "d_bakery"), repo)
    ojas_result = _review(_payload("ojas_fitness", shared_text, "d_ojas"), repo)

    # Neither brand configures a forbidden-guarantee or factual rule for this
    # phrase, so the generic pipeline reports no fabricated contraindication.
    assert bakery_result.findings == []
    assert ojas_result.findings == []

    ledger_repo = _repository_with("ledgerpro_finance")
    fin_result = _review(_payload("ledgerpro_finance", shared_text, "d_fin"), ledger_repo)
    assert any(f.category.value == "wrong_fact" for f in fin_result.findings)


# ---------------------------------------------------------------- Scenario D
def test_scenario_d_brand_isolation_each_brand_gets_own_review():
    repo = _repository_with(*FIVE_BRAND_FIXTURES)

    ojas = _review(_payload("ojas_fitness", OJAS_DRAFT, "iso_1"), repo)
    bakery = _review(_payload("crumb_and_rye_bakery", BAKERY_VIOLATION_DRAFT, "iso_2"), repo)
    fin = _review(_payload("ledgerpro_finance", FINANCIAL_GUARANTEE_DRAFT, "iso_3"), repo)

    # Each result carries its own brand id and policy-sourced findings.
    assert ojas.brand_id == "ojas_fitness"
    assert bakery.brand_id == "crumb_and_rye_bakery"
    assert fin.brand_id == "ledgerpro_finance"

    assert ojas.findings == []
    assert {f.highlighted_text for f in bakery.findings} == {"Crumb&Rye"}
    assert any(f.category.value == "wrong_fact" for f in fin.findings)

    # No cross-brand leakage in explanations, fixes, or rewrites.
    for result in (ojas, bakery, fin):
        blob = json.dumps(
            {
                "findings": [f.model_dump() for f in result.findings],
                "rewrite": result.proposed_rewrite,
            }
        ).lower()
        assert "nimbus" not in blob
    # Bakery's fix mentions Crumb & Rye, never OJAS/Nimbus/LedgerPro.
    if bakery.proposed_rewrite:
        assert "Crumb & Rye" in bakery.proposed_rewrite
        assert "OJAS" not in bakery.proposed_rewrite
        assert "LedgerPro" not in bakery.proposed_rewrite


def test_scenario_d_repeated_requests_are_not_cross_brand_cached():
    repo = _repository_with(*FIVE_BRAND_FIXTURES)
    first = _review(_payload("ledgerpro_finance", FINANCIAL_GUARANTEE_DRAFT, "c1"), repo)
    second_after_other_brand = _review(
        _payload("crumb_and_rye_bakery", BAKERY_VIOLATION_DRAFT, "c2"), repo
    )
    third = _review(_payload("ledgerpro_finance", FINANCIAL_GUARANTEE_DRAFT, "c3"), repo)

    identical_ids = [f.finding_id for f in first.findings]
    repeat_ids = [f.finding_id for f in third.findings]
    assert identical_ids == repeat_ids

    # The intervening bakery request had different findings; no cache bleed.
    assert {f.highlighted_text for f in second_after_other_brand.findings} == {"Crumb&Rye"}
    assert {f.highlighted_text for f in first.findings}.isdisjoint(
        {f.highlighted_text for f in second_after_other_brand.findings}
    )


# ---------------------------------------------------------------- Scenario E
def test_scenario_e_missing_brand_returns_clear_error_not_nimbus():
    repo = _repository_with(*FIVE_BRAND_FIXTURES)
    result = _review(_payload("undefined_brand", "Some random draft copy.", "draft_unknown"), repo)

    assert result.completion_status == "incomplete_policy"
    assert result.decision.status == ReviewDecision.RED
    assert "undefined_brand" in result.decision.reason
    assert result.brand_id == "undefined_brand"
    # No silent substitution with the sample brand.
    assert result.brand_id != "nimbus_cloud"
    assert result.findings == []
    assert result.proposed_rewrite is None


# ---------------------------------------------------------------- Scenario F
def test_scenario_f_empty_brand_memory_borrows_nothing(tmp_path):
    store = FileBrandMemoryStore(storage_dir=tmp_path)
    # No record exists for the bakery brand: must not inherit Nimbus data.
    assert store.get_memory("crumb_and_rye_bakery") is None

    repo = _repository_with("crumb_and_rye_bakery")
    result = _review(_payload("crumb_and_rye_bakery", OJAS_DRAFT, "draft_empty_mem"), repo)

    # Review proceeds honestly with zero brand memory: OJAS content is reviewed
    # only against bakery policy and reports no borrowed facts.
    assert result.completion_status == "completed"
    assert all("uptime" not in f.explanation.lower() for f in result.findings)


def test_scenario_f_brand_memory_is_per_brand(tmp_path):
    store = FileBrandMemoryStore(storage_dir=tmp_path)
    ojas_memory_parts = {"brand_id": "ojas_fitness", "brand_name": "OJAS"}

    from ai_engine.schemas.brand_memory import BrandMemory

    store.save_memory(BrandMemory.model_validate(ojas_memory_parts))
    assert store.get_memory("ojas_fitness") is not None
    # Are ojas values isolated to the ojas file?
    assert store.get_memory("crumb_and_rye_bakery") is None
    assert store.get_memory("ledgerpro_finance") is None


# ---------------------------------------------------------------- Scenario G
def test_scenario_g_arbitrary_draft_types_reach_generic_pipeline():
    repo = _repository_with("crumb_and_rye_bakery")
    drafts = {
        "email": (
            "Subject: Preorder open\nHi Sam,\nCrumb & Rye's seasonal bread range "
            "bakes fresh every morning. Reply to preorder."
        ),
        "social_post": "Fresh wood-fired baguettes at the counter today. Crumb & Rye.",
        "announcement": "Crumb & Rye launches its honey oat sourdough this Friday.",
        "non_tech": "Our team volunteers at the city plant nursery every Friday.",
    }
    for kind, text in drafts.items():
        result = _review(
            _payload("crumb_and_rye_bakery", text, f"draft_{kind}"), repo
        )
        assert result.completion_status == "completed", kind
        assert result.metadata.policy_source == "test_fixture"
        # No technology-brand findings invented for non-technical copy.
        assert all("nimbus" not in f.explanation.lower() for f in result.findings)


# ---------------------------------------------------------------- Scenario H
def test_scenario_h_violation_corrected_meaning_preserved():
    repo = _repository_with("crumb_and_rye_bakery")
    result = _review(
        _payload("crumb_and_rye_bakery", BAKERY_VIOLATION_DRAFT, "draft_rw1"), repo
    )

    assert result.proposed_rewrite is not None
    # The fix is the bakery's own approved spelling.
    assert "Crumb&Rye" not in result.proposed_rewrite
    assert "Crumb & Rye" in result.proposed_rewrite
    # All other meaning survived intact.
    for fragment in ("seasonal bread range", "wood-fired baguettes", "Preorder"):
        assert fragment in result.proposed_rewrite
    assert result.rewrite_proposal.is_post_revalidation_passed
    assert result.post_rewrite_decision.status == ReviewDecision.GREEN


def test_scenario_h_clean_draft_unchanged_no_rewrite():
    repo = _repository_with("ledgerpro_finance")
    result = _review(
        _payload("ledgerpro_finance", FINANCIAL_CLEAN_DRAFT, "draft_rw2"), repo
    )
    assert result.proposed_rewrite is None
    assert result.original_text == FINANCIAL_CLEAN_DRAFT


# ------------------------------------------------- Per-request brand resolution
def test_review_service_resolves_explicit_brand_per_request():
    """Confirm the shared review service honors an explicit per-request brand."""
    from engano_backend.review_service import ReviewService, ReviewSettings

    repo = _repository_with("crumb_and_rye_bakery", "ojas_fitness", include_nimbus=False)
    tmp_path = Path("/tmp/engano_test_memory_no_fallback")
    service = ReviewService(
        ReviewSettings(brand_id="crumb_and_rye_bakery", policy_source="fixture"),
        repository=repo,
        memory_store=FileBrandMemoryStore(storage_dir=tmp_path),
    )

    result = asyncio.run(
        service.review_text("svc_1", OJAS_DRAFT, brand_id="ojas_fitness")
    )
    assert result.brand_id == "ojas_fitness"
    assert result.findings == []

    default_result = asyncio.run(service.review_text("svc_2", BAKERY_VIOLATION_DRAFT))
    assert default_result.brand_id == "crumb_and_rye_bakery"
    assert {f.highlighted_text for f in default_result.findings} == {"Crumb&Rye"}


def test_review_service_empty_brand_resolution_raises_clear_error():
    from engano_backend.review_service import ReviewService, ReviewSettings

    service = ReviewService(
        ReviewSettings(brand_id="anything", policy_source="fixture"),
        repository=MockPolicyRepository(),
        memory_store=FileBrandMemoryStore(storage_dir="/tmp/engano_test_memory_none"),
    )
    with pytest.raises(ValueError, match="No brand could be resolved"):
        service.resolve_brand_id("   ")
