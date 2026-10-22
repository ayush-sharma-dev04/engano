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


def test_supabase_unconfigured_never_substitutes_fixtures():
    # When Supabase is not configured, get_policy must raise rather than silently fallback
    repo = SupabasePolicyRepository(config=EngineConfig(SUPABASE_URL="", SUPABASE_PUBLISHABLE_KEY=""))
    with pytest.raises(RuntimeError) as exc:
        repo.get_policy("nimbus_cloud")
    assert "Supabase integration is unconfigured" in str(exc.value)


def test_supabase_permission_error():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Permission denied: RLS violation"
    mock_client.get.return_value = mock_resp

    repo = SupabasePolicyRepository(
        config=EngineConfig(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="mock-anon-key",
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
            SUPABASE_PUBLISHABLE_KEY="mock-anon-key",
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
            SUPABASE_PUBLISHABLE_KEY="mock-anon-key",
        ),
        http_client=mock_client,
    )
    policy = repo.get_policy("nimbus_cloud")
    assert policy is not None
    assert policy.brand_id == "nimbus_cloud"
    assert policy.brand_name == "Nimbus Cloud"
