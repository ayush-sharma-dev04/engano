"""Tests for AI review providers and factory."""

import json
from unittest.mock import MagicMock, patch
import httpx
import pytest
from google.genai import errors as genai_errors
from ai_engine.config import EngineConfig, ProviderType
from ai_engine.providers.factory import RulesOnlyProvider, get_provider
from ai_engine.providers.gemini import GeminiProvider
from ai_engine.providers.ollama import OllamaProvider
from ai_engine.schemas.brand_policy import BrandPolicy


def test_factory_rules_only():
    provider = get_provider(ProviderType.RULES_ONLY)
    assert isinstance(provider, RulesOnlyProvider)


def test_rules_only_execution_no_network(nimbus_policy: BrandPolicy):
    provider = RulesOnlyProvider()
    resp = provider.review(
        content_text="Draft content",
        policy=nimbus_policy,
        deterministic_findings=[],
    )
    assert resp.provider_name == "rules_only"
    assert resp.findings == []


def test_gemini_missing_api_key_raises_clean_error():
    config = EngineConfig(AI_PROVIDER="gemini", GEMINI_API_KEY="")
    with pytest.raises(ValueError) as exc:
        GeminiProvider(config=config, client=None)
    assert "GEMINI_API_KEY is required" in str(exc.value)


def test_gemini_provider_mocked_success(nimbus_policy: BrandPolicy):
    # Mock the genai Client and response
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "findings": [
            {
                "finding_id": "gem_1",
                "category": "tone_mismatch",
                "severity": "medium",
                "highlighted_text": "hype words",
                "start": 0,
                "end": 10,
                "explanation": "Tone is too aggressive",
                "evidence_status": "unsupported",
            }
        ]
    })
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(
        config=EngineConfig(AI_PROVIDER="gemini", GEMINI_API_KEY="test-mock-key"),
        client=mock_client,
    )
    resp = provider.review("hype words text", nimbus_policy, [])
    assert resp.provider_name == "gemini"
    assert len(resp.findings) == 1
    assert resp.findings[0].category.value == "tone_mismatch"


def test_gemini_malformed_json_fallback(nimbus_policy: BrandPolicy):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "This is not valid JSON at all."
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(
        config=EngineConfig(AI_PROVIDER="gemini", GEMINI_API_KEY="test-mock-key"),
        client=mock_client,
    )
    resp = provider.review("sample text", nimbus_policy, [])
    # Should safely return empty semantic findings without crashing
    assert resp.findings == []


def test_gemini_high_demand_retries_fallback(nimbus_policy: BrandPolicy):
    mock_client = MagicMock()
    primary_error = genai_errors.APIError(
        503,
        {"error": {"message": "This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later."}},
    )
    mock_client.models.generate_content.side_effect = [
        primary_error,
        MagicMock(text=json.dumps({"findings": []})),
    ]

    provider = GeminiProvider(
        config=EngineConfig(AI_PROVIDER="gemini", GEMINI_API_KEY="test-mock-key", GEMINI_MODEL="gemini-3.1-flash-lite"),
        client=mock_client,
    )
    resp = provider.review("sample text", nimbus_policy, [])
    assert resp.provider_name == "gemini"
    assert resp.findings == []
    assert mock_client.models.generate_content.call_count == 2
    assert mock_client.models.generate_content.call_args_list[1].kwargs["model"] == "gemini-3.8-flash"


def test_ollama_connection_error_handling(nimbus_policy: BrandPolicy):
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.ConnectError("Connection refused")

    provider = OllamaProvider(
        config=EngineConfig(AI_PROVIDER="ollama", OLLAMA_BASE_URL="http://127.0.0.1:99999"),
        http_client=mock_client,
    )
    with pytest.raises(RuntimeError) as exc:
        provider.review("text", nimbus_policy, [])
    assert "Ollama service unavailable" in str(exc.value)


def test_ollama_timeout_handling(nimbus_policy: BrandPolicy):
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.TimeoutException("Read timed out")

    provider = OllamaProvider(
        config=EngineConfig(AI_PROVIDER="ollama", REQUEST_TIMEOUT_SECONDS=5.0),
        http_client=mock_client,
    )
    with pytest.raises(RuntimeError) as exc:
        provider.review("text", nimbus_policy, [])
    assert "timed out after" in str(exc.value)


def test_ollama_malformed_response(nimbus_policy: BrandPolicy):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "Malformed non-json output"}
    mock_client.post.return_value = mock_resp

    provider = OllamaProvider(
        config=EngineConfig(AI_PROVIDER="ollama"),
        http_client=mock_client,
    )
    resp = provider.review("text", nimbus_policy, [])
    assert resp.findings == []
