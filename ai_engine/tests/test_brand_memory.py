"""Tests for Persistent, Reusable Brand Memory and Rule Supremacy.

Covers:
- Loading brand profile on a new review without re-entering context
- Saved context surviving restarts (file-backed persistent storage)
- Updating approved brand preferences
- Brand isolation (brand A cannot read/overwrite brand B)
- Error handling for missing or corrupt memory
- Absolute supremacy of BrandPolicy rules over BrandMemory
- Backend API endpoints for brand memory
"""

import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from ai_engine.agents.coordinator import CoordinatorAgent
from ai_engine.config import EngineConfig
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.memory.store import FileBrandMemoryStore, SupabaseBrandMemoryStore
from ai_engine.providers.factory import RulesOnlyProvider
from ai_engine.schemas.brand_memory import BrandMemory
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.payload import DraftPayload
from ai_engine.schemas.review import ReviewDecision
from engano_backend.app import create_app
from engano_backend.review_service import ReviewService, ReviewSettings


@pytest.fixture
def temp_memory_dir(tmp_path: Path) -> Path:
    mem_dir = tmp_path / "brand_memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    return mem_dir


@pytest.fixture
def file_store(temp_memory_dir: Path) -> FileBrandMemoryStore:
    return FileBrandMemoryStore(storage_dir=temp_memory_dir)


def test_save_and_retrieve_brand_memory(file_store: FileBrandMemoryStore):
    """Memory is saved and reloaded with exact field validation."""
    memory = BrandMemory(
        brand_id="brand_alpha",
        brand_name="Brand Alpha",
        description="Enterprise analytics platform",
        voice_and_tone_preferences=["authoritative", "concise"],
        target_audience="CTOs",
        approved_terminology=["AlphaCloud"],
        verified_facts=["Processes 1M events/sec"],
    )
    file_store.save_memory(memory)

    loaded = file_store.get_memory("brand_alpha")
    assert loaded is not None
    assert loaded.brand_id == "brand_alpha"
    assert loaded.brand_name == "Brand Alpha"
    assert "authoritative" in loaded.voice_and_tone_preferences
    assert loaded.target_audience == "CTOs"
    assert loaded.version == 1


def test_survives_backend_restart(temp_memory_dir: Path):
    """Saved context persists on disk across simulated service restarts."""
    # First instance saves memory
    store1 = FileBrandMemoryStore(storage_dir=temp_memory_dir)
    store1.save_memory(BrandMemory(
        brand_id="restart_brand",
        brand_name="Restart Brand",
        target_audience="DevOps Engineers",
    ))

    # Second instance (simulating backend reboot) reads from same storage dir
    store2 = FileBrandMemoryStore(storage_dir=temp_memory_dir)
    loaded = store2.get_memory("restart_brand")
    assert loaded is not None
    assert loaded.brand_name == "Restart Brand"
    assert loaded.target_audience == "DevOps Engineers"


def test_brand_isolation_prevents_leakage(file_store: FileBrandMemoryStore):
    """Brand Alpha cannot read or overwrite Brand Beta's memory."""
    mem_a = BrandMemory(brand_id="brand_a", brand_name="Brand A", target_audience="Audience A")
    mem_b = BrandMemory(brand_id="brand_b", brand_name="Brand B", target_audience="Audience B")

    file_store.save_memory(mem_a)
    file_store.save_memory(mem_b)

    loaded_a = file_store.get_memory("brand_a")
    loaded_b = file_store.get_memory("brand_b")

    assert loaded_a is not None and loaded_b is not None
    assert loaded_a.target_audience == "Audience A"
    assert loaded_b.target_audience == "Audience B"

    # Querying a non-existent brand returns None
    assert file_store.get_memory("brand_c") is None


def test_update_brand_memory_increments_version(file_store: FileBrandMemoryStore):
    """Updating preferences increments version and preserves unchanged attributes."""
    mem = BrandMemory(
        brand_id="update_test",
        brand_name="Original Name",
        voice_and_tone_preferences=["friendly"],
        version=1,
    )
    file_store.save_memory(mem)

    updated = file_store.update_preferences("update_test", {
        "voice_and_tone_preferences": ["professional", "technical"],
    })
    assert updated.version == 2
    assert updated.voice_and_tone_preferences == ["professional", "technical"]
    assert updated.brand_name == "Original Name"


def test_memory_never_overrides_authoritative_rules(nimbus_policy: BrandPolicy, file_store: FileBrandMemoryStore):
    """Brand memory cannot legalize a prohibited claim or bypass policy rules."""
    # Memory claims 100% uptime is verified
    memory = BrandMemory(
        brand_id="nimbus_cloud",
        brand_name="Nimbus Cloud",
        verified_facts=["100% uptime guaranteed"],  # Conflicts with policy rule!
    )
    file_store.save_memory(memory)

    repo = MockPolicyRepository()
    repo.register_policy(nimbus_policy)

    coordinator = CoordinatorAgent(
        repository=repo,
        provider=RulesOnlyProvider(),
        brand_memory=memory,
    )

    draft = "Nimbus DB guarantees 100% uptime."
    payload = DraftPayload(draft_id="safety_check", brand_id="nimbus_cloud", content_text=draft)
    result = coordinator.run_review(payload)

    # Policy supremacy: 100% uptime MUST be flagged as violation despite brand memory
    assert result.decision.status == ReviewDecision.RED
    assert any("100% uptime" in f.highlighted_text for f in result.findings)


def test_corrupt_memory_file_raises_explicit_error(temp_memory_dir: Path):
    """Corrupted memory file raises explicit ValueError and does not masquerade as valid."""
    bad_file = temp_memory_dir / "corrupted_brand.json"
    bad_file.write_text("{this is not valid json!}", encoding="utf-8")

    store = FileBrandMemoryStore(storage_dir=temp_memory_dir)
    with pytest.raises(ValueError) as exc:
        store.get_memory("corrupted_brand")
    assert "Corrupted brand memory record" in str(exc.value)


def test_supabase_memory_store_unconfigured_error():
    """Unconfigured Supabase memory store raises explicit configuration error."""
    store = SupabaseBrandMemoryStore(config=EngineConfig(supabase_url=None, supabase_publishable_key=None))
    with pytest.raises(RuntimeError) as exc:
        store.get_memory("test_brand")
    assert "SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are required" in str(exc.value)


def test_backend_brand_memory_api_endpoints(temp_memory_dir: Path, nimbus_policy: BrandPolicy):
    """Backend FastAPI app serves GET and PUT brand memory endpoints correctly."""
    repo = MockPolicyRepository()
    repo.register_policy(nimbus_policy)
    mem_store = FileBrandMemoryStore(storage_dir=temp_memory_dir)
    mem_store.save_memory(BrandMemory(
        brand_id="nimbus_cloud",
        brand_name="Nimbus Cloud",
        target_audience="Architects",
    ))

    settings = ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture")
    service = ReviewService(settings=settings, repository=repo, memory_store=mem_store)
    app = create_app(review_service=service)
    client = TestClient(app)

    # GET active brand memory
    resp = client.get("/api/brand-memory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["brand_id"] == "nimbus_cloud"
    assert data["target_audience"] == "Architects"

    # PUT update active brand memory
    put_resp = client.put("/api/brand-memory", json={"target_audience": "Senior Executives"})
    assert put_resp.status_code == 200
    assert put_resp.json()["target_audience"] == "Senior Executives"
    assert put_resp.json()["version"] == 2

    # GET missing brand returns 404
    missing_resp = client.get("/api/brand-memory/non_existent_brand")
    assert missing_resp.status_code == 404
