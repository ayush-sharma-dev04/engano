"""Tests for deterministic WCAG accessibility evaluator."""

from ai_engine.rules.accessibility import evaluate_accessibility
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import FindingCategory, FindingSeverity
from ai_engine.schemas.review import VisualMetadata


def test_normal_text_contrast_failure(nimbus_policy: BrandPolicy):
    meta = VisualMetadata(contrast_ratio=3.8, is_large_text=False)
    findings = evaluate_accessibility(meta, nimbus_policy)
    assert len(findings) == 1
    assert findings[0].category == FindingCategory.VISUAL_WCAG
    assert findings[0].severity == FindingSeverity.HIGH
    assert "fails WCAG AA standard" in findings[0].explanation


def test_normal_text_contrast_pass(nimbus_policy: BrandPolicy):
    meta = VisualMetadata(contrast_ratio=4.6, is_large_text=False)
    findings = evaluate_accessibility(meta, nimbus_policy)
    assert len(findings) == 0


def test_large_text_contrast_threshold(nimbus_policy: BrandPolicy):
    # 2.8 fails for large text (< 3.0:1)
    meta_fail = VisualMetadata(contrast_ratio=2.8, is_large_text=True)
    findings_fail = evaluate_accessibility(meta_fail, nimbus_policy)
    assert len(findings_fail) == 1

    # 3.2 passes for large text (>= 3.0:1)
    meta_pass = VisualMetadata(contrast_ratio=3.2, is_large_text=True)
    findings_pass = evaluate_accessibility(meta_pass, nimbus_policy)
    assert len(findings_pass) == 0


def test_missing_alt_text(nimbus_policy: BrandPolicy):
    meta = VisualMetadata(has_alt_text=False)
    findings = evaluate_accessibility(meta, nimbus_policy)
    assert len(findings) == 1
    assert findings[0].category == FindingCategory.VISUAL_WCAG
    assert "missing required descriptive alternative text" in findings[0].explanation


def test_no_metadata_does_not_invent_inspection(nimbus_policy: BrandPolicy):
    findings = evaluate_accessibility(None, nimbus_policy)
    assert len(findings) == 0
