"""Tests for Supabase policy repository boundary."""

from unittest.mock import MagicMock
import httpx
import pytest
from ai_engine.config import EngineConfig
from ai_engine.integrations.supabase_policy_repository import (
    MockPolicyRepository,
    SupabasePolicyRepository,
)
from ai_engine.schemas.brand_policy import BrandPolicy


def test_mock_repository_retrieval(nimbus_policy: BrandPolicy):
    repo = MockPolicyRepository()
    repo.register_policy(nimbus_policy)
    retrieved = repo.get_policy("nimbus_cloud")
    assert retrieved is not None
    assert retrieved.brand_name == "Nimbus Cloud"


def test_mock_repository_missing_brand():
    repo = MockPolicyRepository()
    assert repo.get_policy("nonexistent_brand") is None


def test_supabase_unconfigured_raises_without_secret_key():
    """When SUPABASE_SECRET_KEY is missing, get_policy must raise rather than silently fallback."""
    repo = SupabasePolicyRepository(config=EngineConfig(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY=None,
    ))
    with pytest.raises(RuntimeError) as exc:
        repo.get_policy("nimbus_cloud")
    assert "SUPABASE_SECRET_KEY" in str(exc.value)


def test_supabase_unconfigured_raises_without_url():
    """When SUPABASE_URL is missing, get_policy must raise."""
    repo = SupabasePolicyRepository(config=EngineConfig(
        SUPABASE_URL="",
        SUPABASE_SECRET_KEY="mock-secret",
    ))
    with pytest.raises(RuntimeError) as exc:
        repo.get_policy("nimbus_cloud")
    assert "SUPABASE_URL" in str(exc.value)


def test_supabase_unconfigured_both_missing():
    """When both URL and key are missing, get_policy must raise."""
    repo = SupabasePolicyRepository(config=EngineConfig(
        SUPABASE_URL="",
        SUPABASE_SECRET_KEY=None,
    ))
    with pytest.raises(RuntimeError) as exc:
        repo.get_policy("nimbus_cloud")
    assert "unconfigured" in str(exc.value).lower()


def test_supabase_publishable_key_alone_is_insufficient():
    """A publishable key without a secret key cannot authorize server-side policy access."""
    repo = SupabasePolicyRepository(config=EngineConfig(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="anon-key",
        SUPABASE_SECRET_KEY=None,
    ))
    with pytest.raises(RuntimeError) as exc:
        repo.get_policy("nimbus_cloud")
    assert "SUPABASE_SECRET_KEY" in str(exc.value)


def test_supabase_permission_error():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Permission denied: RLS violation"
    mock_client.get.return_value = mock_resp

    repo = SupabasePolicyRepository(
        config=EngineConfig(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_SECRET_KEY="mock-service-role-key",
        ),
        http_client=mock_client,
    )
    with pytest.raises(PermissionError) as exc:
        repo.get_policy("any_brand")
    assert "access denied" in str(exc.value).lower()


def test_supabase_connectivity_failure():
    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.RequestError("Host lookup failed")

    repo = SupabasePolicyRepository(
        config=EngineConfig(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_SECRET_KEY="mock-service-role-key",
        ),
        http_client=mock_client,
    )
    with pytest.raises(RuntimeError) as exc:
        repo.get_policy("any_brand")
    assert "Failed to connect to Supabase" in str(exc.value)


def test_supabase_successful_deserialization(nimbus_policy: BrandPolicy):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [nimbus_policy.model_dump(mode="json")]
    mock_client.get.return_value = mock_resp

    repo = SupabasePolicyRepository(
        config=EngineConfig(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_SECRET_KEY="mock-service-role-key",
        ),
        http_client=mock_client,
    )
    policy = repo.get_policy("nimbus_cloud")
    assert policy is not None
    assert policy.brand_id == "nimbus_cloud"
    assert policy.brand_name == "Nimbus Cloud"


def test_supabase_authenticated_request_uses_service_role_key():
    """Verify the HTTP request carries the secret key in the apikey header, not the anon key."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    mock_client.get.return_value = mock_resp

    repo = SupabasePolicyRepository(
        config=EngineConfig(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="anon-key-should-not-appear",
            SUPABASE_SECRET_KEY="mock-service-role-key",
        ),
        http_client=mock_client,
    )
    repo.get_policy("nimbus_cloud")

    # Inspect the actual call
    mock_client.get.assert_called_once()
    call_kwargs = mock_client.get.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
    assert headers["apikey"] == "mock-service-role-key"
    # Must NOT contain the anon/publishable key
    assert "anon-key-should-not-appear" not in str(headers)


def test_supabase_brand_not_found_returns_none():
    """Query returning empty array yields None, not an error."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    mock_client.get.return_value = mock_resp

    repo = SupabasePolicyRepository(
        config=EngineConfig(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_SECRET_KEY="mock-service-role-key",
        ),
        http_client=mock_client,
    )
    assert repo.get_policy("nonexistent_brand") is None


def test_supabase_server_error():
    """Non-200 non-auth status codes raise RuntimeError."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_client.get.return_value = mock_resp

    repo = SupabasePolicyRepository(
        config=EngineConfig(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_SECRET_KEY="mock-service-role-key",
        ),
        http_client=mock_client,
    )
    with pytest.raises(RuntimeError) as exc:
        repo.get_policy("any_brand")
    assert "HTTP 500" in str(exc.value)
