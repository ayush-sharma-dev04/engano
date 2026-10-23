"""Comprehensive Reality and Integration Tests for AI Review Providers.

Distinguishes between:
- Offline mocked tests
- Real cloud integration tests (Google Gemini)
- Real local integration tests (Ollama Qwen 2.5 VL 3B)
- Deterministic rules-only execution
- Dynamic provider configuration and runtime switching
"""

import os
from unittest.mock import MagicMock
import httpx
import pytest
from ai_engine.config import EngineConfig, ProviderType
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.providers.factory import RulesOnlyProvider, get_provider
from ai_engine.providers.gemini import GeminiProvider
from ai_engine.providers.ollama import OllamaProvider
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import Finding, FindingCategory, FindingSeverity, TextSpan
from ai_engine.schemas.payload import DraftPayload
from ai_engine.agents.coordinator import CoordinatorAgent


def test_invalid_provider_name_raises_clear_error():
    """Invalid AI_PROVIDER produces clear ValueError naming valid options."""
    with pytest.raises(ValueError) as exc:
        EngineConfig(AI_PROVIDER="unsupported_ai_vendor")
    assert "Invalid AI_PROVIDER" in str(exc.value)
    assert "rules_only" in str(exc.value)


def test_provider_factory_selection():
    """Factory correctly resolves all provider types."""
    assert isinstance(get_provider(ProviderType.RULES_ONLY), RulesOnlyProvider)
    assert isinstance(get_provider(ProviderType.OLLAMA), OllamaProvider)
    # Gemini requires API key to construct client
    gemini_cfg = EngineConfig(AI_PROVIDER="gemini", GEMINI_API_KEY="dummy-key-for-factory-test")
    assert isinstance(get_provider(ProviderType.GEMINI, config=gemini_cfg), GeminiProvider)


def test_rules_only_execution_independent_of_cloud_and_local(nimbus_policy: BrandPolicy):
    """RulesOnlyProvider runs deterministically without network calls or external models."""
    provider = RulesOnlyProvider()
    resp = provider.review("Nimbus DB is great", nimbus_policy, [])
    assert resp.provider_name == "rules_only"
    assert resp.findings == []
    assert resp.latency_ms == 0.0


def test_gemini_missing_credentials_raises_error():
    """GeminiProvider refuses to initialize without an API key."""
    cfg = EngineConfig(AI_PROVIDER="gemini", GEMINI_API_KEY="")
    with pytest.raises(ValueError) as exc:
        GeminiProvider(config=cfg, client=None)
    assert "GEMINI_API_KEY is required" in str(exc.value)


def test_ollama_unreachable_server_fails_safely(nimbus_policy: BrandPolicy):
    """OllamaProvider raises clean error when daemon is offline."""
    cfg = EngineConfig(
        AI_PROVIDER="ollama",
        OLLAMA_BASE_URL="http://127.0.0.1:54321",  # Unused port
        REQUEST_TIMEOUT_SECONDS=2.0,
    )
    provider = OllamaProvider(config=cfg)
    with pytest.raises(RuntimeError) as exc:
        provider.review("Test copy", nimbus_policy, [])
    assert "Ollama service unavailable" in str(exc.value)


# ---------------------------------------------------------------------------
# REAL INTEGRATION TESTS (Executed when real services/credentials exist)
# ---------------------------------------------------------------------------

def _is_live_gemini_available() -> bool:
    try:
        from ai_engine.config import get_engine_config
        cfg = get_engine_config()
        if cfg.gemini_api_key:
            val = cfg.gemini_api_key.get_secret_value()
            return bool(val and val.strip())
        return False
    except Exception:
        return False


def _is_live_ollama_available() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if r.status_code == 200:
            models = [m.get("name") for m in r.json().get("models", [])]
            return any("qwen2.5vl:3b" in m for m in models)
        return False
    except Exception:
        return False


@pytest.mark.skipif(not _is_live_gemini_available(), reason="Live GEMINI_API_KEY not configured")
def test_real_gemini_invocation_end_to_end(nimbus_policy: BrandPolicy):
    """Live Google Gemini inference test using genuine credentials from environment."""
    cfg = EngineConfig(
        AI_PROVIDER="gemini",
        GEMINI_MODEL="gemini-3.1-flash-lite",  # High-availability fast model
    )
    provider = GeminiProvider(config=cfg)
    resp = provider.review(
        content_text="Nimbus DB provides fast cloud storage with 99.95% uptime.",
        policy=nimbus_policy,
        deterministic_findings=[],
    )
    assert resp.provider_name == "gemini"
    assert resp.latency_ms > 0.0
    assert isinstance(resp.findings, list)


@pytest.mark.skipif(not _is_live_ollama_available(), reason="Local Ollama daemon or qwen2.5vl:3b not available")
def test_real_ollama_invocation_end_to_end(nimbus_policy: BrandPolicy):
    """Live Ollama local inference test using running daemon and qwen2.5vl:3b model."""
    cfg = EngineConfig(
        AI_PROVIDER="ollama",
        OLLAMA_BASE_URL="http://localhost:11434",
        OLLAMA_MODEL="qwen2.5vl:3b",
        REQUEST_TIMEOUT_SECONDS=30.0,
    )
    provider = OllamaProvider(config=cfg)
    resp = provider.review(
        content_text="Nimbus DB provides secure database storage.",
        policy=nimbus_policy,
        deterministic_findings=[],
    )
    assert resp.provider_name == "ollama"
    assert resp.latency_ms > 0.0
    assert isinstance(resp.findings, list)


def test_coordinator_provider_runtime_switching(nimbus_policy: BrandPolicy):
    """CoordinatorAgent respects explicitly supplied provider instances."""
    repo = MockPolicyRepository()
    repo.register_policy(nimbus_policy)
    payload = DraftPayload(draft_id="switch_1", brand_id="nimbus_cloud", content_text="Clean draft copy.")

    # 1. Rules-only
    coord_rules = CoordinatorAgent(repository=repo, provider=RulesOnlyProvider())
    res_rules = coord_rules.run_review(payload)
    assert res_rules.metadata.provider_selected == "rules_only"
    assert "SemanticProvider" not in res_rules.metadata.agents_executed

    # 2. Mocked LLM provider
    mock_provider = MagicMock()
    mock_provider.provider_name = "mock_ai"
    mock_provider.review.return_value = MagicMock(
        provider_name="mock_ai",
        findings=[],
        raw_response="{}",
        latency_ms=12.5,
    )
    coord_mock = CoordinatorAgent(repository=repo, provider=mock_provider)
    res_mock = coord_mock.run_review(payload)
    assert "SemanticProvider" in res_mock.metadata.agents_executed
    assert mock_provider.review.called
