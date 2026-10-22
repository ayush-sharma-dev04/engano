"""Tests for deterministic terminology evaluator."""

from ai_engine.rules.terminology import evaluate_terminology
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import FindingCategory, FindingSeverity


def test_flags_prohibited_variant_nimbusdb(nimbus_policy: BrandPolicy):
    text = "Deploy your application on NimbusDB today."
    findings = evaluate_terminology(text, nimbus_policy)
    assert len(findings) == 1
    f = findings[0]
    assert f.category == FindingCategory.TERMINOLOGY
    assert f.severity == FindingSeverity.MEDIUM
    assert f.highlighted_text == "NimbusDB"
    assert text[f.text_span.start : f.text_span.end] == "NimbusDB"
    assert f.suggested_fix == "Nimbus DB"


def test_flags_hyphenated_variant(nimbus_policy: BrandPolicy):
    text = "We love Nimbus-DB for production workloads."
    findings = evaluate_terminology(text, nimbus_policy)
    assert len(findings) == 1
    f = findings[0]
    assert f.highlighted_text == "Nimbus-DB"
    assert text[f.text_span.start : f.text_span.end] == "Nimbus-DB"


def test_approved_terminology_no_false_positive(nimbus_policy: BrandPolicy):
    text = "Deploy your application on Nimbus DB today."
    findings = evaluate_terminology(text, nimbus_policy)
    assert len(findings) == 0


def test_word_boundary_safety(nimbus_policy: BrandPolicy):
    # Prohibited variant NimbusDB inside another compound word should not false trigger
    text = "The system uses PseudoNimbusDBEngine in test environments."
    findings = evaluate_terminology(text, nimbus_policy)
    assert len(findings) == 0


def test_case_insensitive_handling(nimbus_policy: BrandPolicy):
    text = "Check out nimbusdb performance."
    findings = evaluate_terminology(text, nimbus_policy)
    assert len(findings) == 1
    assert findings[0].highlighted_text == "nimbusdb"
    assert findings[0].suggested_fix == "Nimbus DB"
