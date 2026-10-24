"""Focused regression tests for the engine handoff fixes."""

from unittest.mock import MagicMock
import re
import pytest
from ai_engine.config import EngineConfig
from ai_engine.agents.evidence_validation import EvidenceValidationAgent
from ai_engine.agents.rewrite import RewriteAgent
from ai_engine.providers.ollama import OllamaProvider
from ai_engine.rules.claims import evaluate_claims
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)
from ai_engine.schemas.payload import ImageItem
from ai_engine.providers.base import BaseProvider, ProviderResponse


def test_default_request_timeout_is_120_seconds():
    assert EngineConfig.model_fields["request_timeout_seconds"].default == 120.0


def test_ollama_sends_keep_alive_and_uses_default_timeout(nimbus_policy: BrandPolicy):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": '{"findings": []}'}
    mock_client.post.return_value = mock_resp

    config = EngineConfig(AI_PROVIDER="ollama", REQUEST_TIMEOUT_SECONDS=120.0)
    provider = OllamaProvider(config=config, http_client=mock_client)

    assert provider.timeout == 120.0

    provider.review("text", nimbus_policy, [])
    sent_payload = mock_client.post.call_args.kwargs["json"]
    assert sent_payload["keep_alive"] == "1h"
    assert sent_payload["model"] == config.ollama_model


def test_risk_free_detected_as_absolute_legal_claim(nimbus_policy: BrandPolicy):
    findings = evaluate_claims("Our product is risk-free for everyone.", nimbus_policy)
    f = next(f for f in findings if "risk-free" in f.highlighted_text.lower())
    assert f.category == FindingCategory.UNSUPPORTED_CLAIM
    assert f.severity == FindingSeverity.HIGH
    assert f.text_span.end > f.text_span.start
    assert nimbus_policy.model_dump()  # sanity: still valid policy


def test_fully_compliant_with_every_law_detected(nimbus_policy: BrandPolicy):
    findings = evaluate_claims(
        "We are fully compliant with every law in every jurisdiction.",
        nimbus_policy,
    )
    f = next(f for f in findings if "fully compliant with every law" in f.highlighted_text.lower())
    assert f.category == FindingCategory.UNSUPPORTED_CLAIM
    assert f.severity == FindingSeverity.HIGH


def test_competitor_putdown_detected(nimbus_policy: BrandPolicy):
    findings = evaluate_claims("Our rivals are a joke, but our product wins.", nimbus_policy)
    putdowns = [f for f in findings if f.category == FindingCategory.TONE_MISMATCH]
    assert len(putdowns) == 1
    assert "our rivals are a joke" in putdowns[0].highlighted_text.lower()
    assert putdowns[0].severity == FindingSeverity.MEDIUM


def test_clean_draft_has_no_legal_or_putdown_findings(nimbus_policy: BrandPolicy):
    clean = "Nimbus DB is a high-performance database with a 14-day free trial."
    findings = evaluate_claims(clean, nimbus_policy)
    assert not any("risk" in f.highlighted_text.lower() and "free" in f.highlighted_text.lower() for f in findings)
    assert not any(f.category == FindingCategory.TONE_MISMATCH for f in findings)


def test_evidence_validation_filters_finding_supported_by_approved_fact(nimbus_policy: BrandPolicy):
    agent = EvidenceValidationAgent()
    fact_finding = Finding(
        finding_id="ai_false_positive",
        category=FindingCategory.UNSUPPORTED_CLAIM,
        severity=FindingSeverity.HIGH,
        highlighted_text="99.95% monthly uptime SLA",
        text_span=TextSpan(start=0, end=21),
        explanation="AI flagged the approved SLA fact as unsupported",
        evidence_status=EvidenceStatus.UNSUPPORTED,
    )
    result = agent.validate_findings([fact_finding], nimbus_policy, supplied_evidence=None)
    assert result == []


def test_evidence_validation_filters_partial_claim_materially_supported_by_fact(nimbus_policy: BrandPolicy):
    agent = EvidenceValidationAgent()
    # Partial phrasing of the approved fact must still be treated as materially supported
    fact_finding = Finding(
        finding_id="ai_partial_false_positive",
        category=FindingCategory.UNSUPPORTED_CLAIM,
        severity=FindingSeverity.HIGH,
        highlighted_text="99.95% uptime SLA",
        text_span=TextSpan(start=0, end=16),
        explanation="AI flagged a partial restatement of the approved SLA fact",
        evidence_status=EvidenceStatus.UNSUPPORTED,
    )
    result = agent.validate_findings([fact_finding], nimbus_policy, supplied_evidence=None)
    assert result == []


def test_evidence_validation_preserves_brand_subject_finding(nimbus_policy: BrandPolicy):
    agent = EvidenceValidationAgent()
    brand_finding = Finding(
        finding_id="ai_subject_ref",
        category=FindingCategory.UNSUPPORTED_CLAIM,
        severity=FindingSeverity.HIGH,
        highlighted_text="Nimbus Cloud",
        text_span=TextSpan(start=0, end=11),
        explanation="AI named the brand subject",
        evidence_status=EvidenceStatus.UNSUPPORTED,
    )
    result = agent.validate_findings([brand_finding], nimbus_policy, supplied_evidence=None)
    assert len(result) == 1


def test_evidence_validation_preserves_genuine_contradiction(nimbus_policy: BrandPolicy):
    agent = EvidenceValidationAgent()
    contradiction = Finding(
        finding_id="real_contradiction",
        category=FindingCategory.WRONG_FACT,
        severity=FindingSeverity.CRITICAL,
        highlighted_text="100% uptime",
        text_span=TextSpan(start=0, end=11),
        explanation="Contradicts SLA",
        evidence_status=EvidenceStatus.UNSUPPORTED,
    )
    result = agent.validate_findings([contradiction], nimbus_policy, supplied_evidence=None)
    assert len(result) == 1
    assert result[0].evidence_status == EvidenceStatus.CONTRADICTED


# --- Gaps: guaranteed!, accessibility message, image forwarding, LLM rewrite ---


def test_guaranteed_exclamation_detected(nimbus_policy: BrandPolicy):
    findings = evaluate_claims("Our service is guaranteed! and fast.", nimbus_policy)
    g = [f for f in findings if "guaranteed" in f.highlighted_text.lower()]
    assert len(g) == 1
    assert g[0].category == FindingCategory.UNSUPPORTED_CLAIM
    assert g[0].severity == FindingSeverity.HIGH
    assert g[0].suggested_fix == ""
    assert g[0].text_span.end > g[0].text_span.start


def test_bare_guaranteed_without_exclamation_not_flagged(nimbus_policy: BrandPolicy):
    findings = evaluate_claims("Our product is guaranteed.", nimbus_policy)
    assert not any("guaranteed" in f.highlighted_text.lower() for f in findings)


def test_rewrite_strips_guaranteed_so_post_recheck_is_clean(nimbus_policy: BrandPolicy):
    text = "Our service is guaranteed! and fast."
    m = re.search(r"(?<!\w)guaranteed!+(?!\w)", text, re.IGNORECASE)
    span = m.span()
    finding = Finding(
        finding_id="g1",
        category=FindingCategory.UNSUPPORTED_CLAIM,
        severity=FindingSeverity.HIGH,
        highlighted_text=text[span[0]:span[1]],
        text_span=TextSpan(start=span[0], end=span[1]),
        explanation="Absolute guarantee prohibited",
        evidence_status=EvidenceStatus.UNSUPPORTED,
        suggested_fix="",
        human_review_required=True,
    )
    proposal = RewriteAgent().generate_rewrite(text, [finding], nimbus_policy)
    assert "guaranteed!" not in proposal.proposed_text
    assert proposal.is_post_revalidation_passed is True
    assert len(proposal.unresolved_findings) == 0
    assert len(proposal.new_findings) == 0


def test_accessibility_only_unfixable_uses_non_alarming_message(nimbus_policy: BrandPolicy):
    alt = Finding(
        finding_id="a11y_img_missing_alt_0",
        category=FindingCategory.VISUAL_WCAG,
        severity=FindingSeverity.MEDIUM,
        highlighted_text="Image #1",
        text_span=TextSpan(start=0, end=0),
        explanation="missing alt text",
        evidence_status=EvidenceStatus.VERIFIED,
        cited_source="WCAG 1.1.1",
        suggested_fix="Add descriptive alt text",
        human_review_required=True,
    )
    proposal = RewriteAgent().generate_rewrite("See our new product image.", [alt], nimbus_policy)
    assert "high-risk policy violations requiring creator revision" not in (proposal.clarification_question or "")
    assert "visual accessibility issues" in proposal.clarification_question
    assert proposal.requires_clarification is True


def test_ollama_review_forwards_images_in_payload(nimbus_policy: BrandPolicy):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": '{"findings": []}'}
    mock_client.post.return_value = mock_resp

    provider = OllamaProvider(
        config=EngineConfig(AI_PROVIDER="ollama", REQUEST_TIMEOUT_SECONDS=5.0),
        http_client=mock_client,
    )
    img = ImageItem(url="https://example.com/img.png", alt_text="demo", mime_type="image/png")
    provider.review("text", nimbus_policy, [], images=[img])

    sent = mock_client.post.call_args.kwargs["json"]
    assert sent["keep_alive"] == "1h"
    assert "images" in sent
    assert "https://example.com/img.png" in sent["images"]


def _make_llm_provider(rewrite_text):
    class _StubLLMProvider(BaseProvider):
        provider_name = "stub_llm"

        def __init__(self, text):
            self._text = text

        def review(self, content_text, policy, deterministic_findings, images=None):
            return ProviderResponse(
                provider_name=self.provider_name, findings=[], raw_response="", latency_ms=0.0
            )

        def generate_rewrite(self, content_text, policy, findings, images=None):
            return self._text

    return _StubLLMProvider(rewrite_text)


def test_rewrite_uses_llm_rewrite_when_clean(nimbus_policy: BrandPolicy):
    text = "NimbusDB is great."
    finding = Finding(
        finding_id="term_nimbusdb",
        category=FindingCategory.TERMINOLOGY,
        severity=FindingSeverity.MEDIUM,
        highlighted_text="NimbusDB",
        text_span=TextSpan(start=0, end=8),
        explanation="Prohibited variant",
        evidence_status=EvidenceStatus.VERIFIED,
        cited_source="Terminology Rule",
        suggested_fix="Nimbus DB",
        human_review_required=False,
    )
    provider = _make_llm_provider("Nimbus DB is excellent.")
    proposal = RewriteAgent().generate_rewrite(text, [finding], nimbus_policy, provider=provider)
    assert proposal.proposed_text == "Nimbus DB is excellent."
    assert any("LLM" in f for f in proposal.applied_fixes)
    assert "llm" in proposal.explanation.lower()


def test_rewrite_falls_back_to_mechanical_when_llm_regresses(nimbus_policy: BrandPolicy):
    text = "NimbusDB is great."
    finding = Finding(
        finding_id="term_nimbusdb",
        category=FindingCategory.TERMINOLOGY,
        severity=FindingSeverity.MEDIUM,
        highlighted_text="NimbusDB",
        text_span=TextSpan(start=0, end=8),
        explanation="Prohibited variant",
        evidence_status=EvidenceStatus.VERIFIED,
        cited_source="Terminology Rule",
        suggested_fix="Nimbus DB",
        human_review_required=False,
    )
    # LLM returns a rewrite that still contains the prohibited variant -> regression
    provider = _make_llm_provider("NimbusDB is excellent.")
    proposal = RewriteAgent().generate_rewrite(text, [finding], nimbus_policy, provider=provider)
    assert proposal.proposed_text == "Nimbus DB is great."
    assert "mechanical" in proposal.explanation

