"""Shared pytest fixtures for offline test suite."""

import json
import os
from pathlib import Path
import pytest
from ai_engine.config import get_engine_config
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.schemas.brand_policy import BrandPolicy

# Default unit tests to rules_only unless a test explicitly configures another provider
os.environ.setdefault("AI_PROVIDER", "rules_only")
get_engine_config.cache_clear()


@pytest.fixture(scope="session")
def fixture_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "brand_library"


@pytest.fixture(scope="session")
def nimbus_policy_path(fixture_dir: Path) -> Path:
    return fixture_dir / "nimbus_db.json"


@pytest.fixture(scope="session")
def nimbus_policy(nimbus_policy_path: Path) -> BrandPolicy:
    data = json.loads(nimbus_policy_path.read_text(encoding="utf-8"))
    return BrandPolicy.model_validate(data)


@pytest.fixture
def mock_repo(nimbus_policy: BrandPolicy) -> MockPolicyRepository:
    repo = MockPolicyRepository()
    repo.register_policy(nimbus_policy)
    return repo


@pytest.fixture
def sample_draft() -> str:
    return "NimbusDB is the fastest database in the world, with 100% uptime. Try it free forever and see why teams love it!"


@pytest.fixture
def clean_draft() -> str:
    return "Nimbus DB is a high-performance database with a 14-day free trial."
