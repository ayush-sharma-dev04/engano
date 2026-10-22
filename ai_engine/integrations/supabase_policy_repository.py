"""Supabase Policy Repository Boundary.

Defines the repository interface and data mapping for brand policies.
Production policies are managed by the database team in Supabase.
Testing and local benchmarks use MockPolicyRepository with explicit fixtures.
"""

from abc import ABC, abstractmethod
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import httpx
from ai_engine.config import EngineConfig, get_engine_config
from ai_engine.schemas.brand_policy import BrandPolicy

logger = logging.getLogger(__name__)


class BasePolicyRepository(ABC):
    """Abstract policy repository interface."""

    @abstractmethod
    def get_policy(self, brand_id: str) -> Optional[BrandPolicy]:
        """Retrieve authoritative brand policy by brand_id.

        Returns None if brand does not exist.
        Raises RuntimeError on operational failure.
        """
        pass


class MockPolicyRepository(BasePolicyRepository):
    """Testing and offline development repository.

    Explicitly isolated for automated tests and local benchmarks.
    Never used silently in production requests.
    """

    def __init__(self, initial_policies: Optional[Dict[str, BrandPolicy]] = None) -> None:
        self._policies: Dict[str, BrandPolicy] = initial_policies or {}

    def register_policy(self, policy: BrandPolicy) -> None:
        """Register a test fixture policy."""
        self._policies[policy.brand_id] = policy

    def load_fixture(self, fixture_path: str | Path) -> BrandPolicy:
        """Load and register a JSON fixture file (such as nimbus_db.json)."""
        path = Path(fixture_path)
        if not path.exists():
            raise FileNotFoundError(f"Policy fixture not found at {path}")
        raw_data = json.loads(path.read_text(encoding="utf-8"))
        policy = BrandPolicy.model_validate(raw_data)
        self.register_policy(policy)
        return policy

    def get_policy(self, brand_id: str) -> Optional[BrandPolicy]:
        return self._policies.get(brand_id)


class SupabasePolicyRepository(BasePolicyRepository):
    """Production Supabase policy repository boundary.

    Connects via authenticated PostgREST API endpoint.
    Respects Row-Level Security (RLS) using publishable anon key.
    Never mutates schema or tables.
    """

    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.config = config or get_engine_config()
        self.supabase_url = self.config.supabase_url
        self.publishable_key = (
            self.config.supabase_publishable_key.get_secret_value()
            if self.config.supabase_publishable_key
            else None
        )
        self.timeout = self.config.request_timeout_seconds
        self._client = http_client or httpx.Client(timeout=self.timeout)

    def get_policy(self, brand_id: str) -> Optional[BrandPolicy]:
        """Fetch authoritative policy from Supabase brand_policies table."""
        if not self.supabase_url or not self.publishable_key:
            raise RuntimeError(
                "Supabase integration is unconfigured. Set SUPABASE_URL and "
                "SUPABASE_PUBLISHABLE_KEY. Production code will not substitute test fixtures."
            )

        headers = {
            "apikey": self.publishable_key,
            "Authorization": f"Bearer {self.publishable_key}",
            "Accept": "application/json",
        }
        endpoint = f"{self.supabase_url.rstrip('/')}/rest/v1/brand_policies"
        params = {"brand_id": f"eq.{brand_id}", "select": "*"}

        try:
            response = self._client.get(endpoint, headers=headers, params=params)
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Failed to connect to Supabase: {type(exc).__name__}: {exc}"
            ) from None

        if response.status_code == 401 or response.status_code == 403:
            raise PermissionError(
                f"Supabase access denied (HTTP {response.status_code}). Check RLS and API key permissions."
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"Supabase policy query returned HTTP {response.status_code}: {response.text}"
            )

        records = response.json()
        if not records or len(records) == 0:
            logger.info("Brand policy '%s' not found in Supabase", brand_id)
            return None

        record: Dict[str, Any] = records[0]

        # Convert database record into validated BrandPolicy model
        try:
            return BrandPolicy.model_validate(record)
        except Exception as exc:
            raise ValueError(
                f"Supabase record for brand '{brand_id}' failed BrandPolicy validation: {exc}"
            ) from exc
