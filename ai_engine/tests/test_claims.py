"""Tests for deterministic claims and factual evaluator."""

from datetime import date
from ai_engine.rules.claims import evaluate_claims
from ai_engine.rules.factual import evaluate_factual
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import EvidenceStatus, FindingCategory, FindingSeverity


def test_unsupported_superlative_claim(nimbus_policy: BrandPolicy):
    text = "We built the fastest database in the world for developers."
    findings = evaluate_claims(text, nimbus_policy, supplied_evidence=None)
    assert len(findings) >= 1
    f = next(f for f in findings if f.category == FindingCategory.UNSUPPORTED_CLAIM)
    assert f.evidence_status == EvidenceStatus.UNSUPPORTED
    assert f.severity == FindingSeverity.HIGH
    assert f.highlighted_text == "fastest database in the world"
    assert text[f.text_span.start : f.text_span.end] == "fastest database in the world"


def test_superlative_with_supplied_benchmark(nimbus_policy: BrandPolicy):
    text = "We built the fastest database in the world for developers."
    evidence = "As demonstrated in Benchmark B-4 internal test results."
    findings = evaluate_claims(text, nimbus_policy, supplied_evidence=evidence)
    assert len(findings) >= 1
    f = next(f for f in findings if f.category == FindingCategory.UNSUPPORTED_CLAIM)
    assert f.evidence_status == EvidenceStatus.UNVERIFIED_PROVIDED


def test_contradicted_uptime_claim(nimbus_policy: BrandPolicy):
    text = "Our platform offers 100% uptime for mission critical services."
    findings = evaluate_claims(text, nimbus_policy)
    f = next(f for f in findings if "100% uptime" in f.highlighted_text)
    assert f.evidence_status == EvidenceStatus.CONTRADICTED
    assert f.severity == FindingSeverity.CRITICAL
    assert f.suggested_fix == "99.95% uptime SLA"


def test_retired_offer_detection(nimbus_policy: BrandPolicy):
    text = "Get started and try it free forever today!"
    findings = evaluate_factual(text, nimbus_policy, current_date=date(2026, 1, 1))
    assert len(findings) == 1
    f = findings[0]
    assert f.category == FindingCategory.OUTDATED_OFFER
    assert f.evidence_status == EvidenceStatus.CONTRADICTED
    assert f.severity == FindingSeverity.HIGH
    assert f.suggested_fix == "14-day free trial"


def test_active_validity_date_not_expired(nimbus_policy: BrandPolicy):
    # During 2025, 14-day free trial is active and should not trigger outdated_offer
    text = "Sign up for our 14-day free trial."
    findings = evaluate_factual(text, nimbus_policy, current_date=date(2025, 6, 1))
    assert len(findings) == 0
