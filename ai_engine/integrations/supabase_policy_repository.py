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

    @property
    def source_name(self) -> str:
        """Human-readable source identifier exposed in review metadata/logs."""
        return type(self).__name__

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

    @property
    def source_name(self) -> str:
        return "test_fixture"

    def __init__(self, initial_policies: Optional[Dict[str, BrandPolicy]] = None) -> None:
        self._policies: Dict[str, BrandPolicy] = initial_policies or {}

    def register_policy(self, policy: BrandPolicy) -> None:
        """Register a test fixture policy."""
        self._policies[policy.brand_id] = policy

    # Alias for convenience in tests
    save_policy = register_policy

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

    Authenticates with the backend-only service-role secret key
    (SUPABASE_SECRET_KEY), consistent with SupabaseBrandMemoryStore.
    The brand_policies table grants access only to service_role;
    anon / authenticated keys will be rejected by RLS.
    Never mutates schema or tables.
    """

    @property
    def source_name(self) -> str:
        return "supabase"

    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.config = config or get_engine_config()
        self.supabase_url = (
            self.config.supabase_url.strip() if self.config.supabase_url else None
        )
        self.secret_key = (
            self.config.supabase_secret_key.get_secret_value().strip()
            if self.config.supabase_secret_key
            else None
        )
        self.timeout = self.config.request_timeout_seconds
        self._client = http_client or httpx.Client(timeout=self.timeout)

    def _get_headers(self) -> Dict[str, str]:
        if not self.supabase_url or not self.secret_key:
            raise RuntimeError(
                "Supabase policy repository unconfigured. "
                "SUPABASE_URL and SUPABASE_SECRET_KEY are required."
            )
        return {
            "apikey": self.secret_key,
            "Accept": "application/json",
        }

    def get_policy(self, brand_id: str) -> Optional[BrandPolicy]:
        """Fetch authoritative policy from Supabase brand_policies table."""
        headers = self._get_headers()
        endpoint = f"{self.supabase_url.rstrip('/')}/rest/v1/brand_policies"
        params = {"brand_id": f"eq.{brand_id}", "select": "*"}

        try:
            response = self._client.get(endpoint, headers=headers, params=params)
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Failed to connect to Supabase: {type(exc).__name__}: {exc}"
            ) from None

        if response.status_code in (401, 403):
            raise PermissionError(
                f"Supabase access denied (HTTP {response.status_code}). "
                "Verify SUPABASE_SECRET_KEY has service_role privileges."
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
