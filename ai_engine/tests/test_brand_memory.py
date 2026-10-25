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
from unittest.mock import MagicMock

import httpx
import pytest
from starlette.testclient import TestClient

from ai_engine.agents.coordinator import CoordinatorAgent
from ai_engine.config import EngineConfig
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.memory.importer import import_brand_memory_records
from ai_engine.memory.store import FileBrandMemoryStore, SupabaseBrandMemoryStore, get_brand_memory_store
from ai_engine.providers.factory import RulesOnlyProvider
from ai_engine.schemas.brand_memory import BrandMemory
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.payload import DraftPayload
from ai_engine.schemas.review import ReviewDecision
from engano_backend.app import create_app
from engano_backend.team_store import TeamStore
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
    """A publishable key alone cannot authorize server-side brand-memory access."""
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_publishable_key="publishable-key",
            supabase_secret_key=None,
        )
    )
    with pytest.raises(RuntimeError) as exc:
        store.get_memory("test_brand")
    assert "SUPABASE_URL and SUPABASE_SECRET_KEY are required" in str(exc.value)


def test_explicit_supabase_store_fails_without_server_secret_key():
    store = get_brand_memory_store(
        config=EngineConfig(
            memory_source="supabase",
            supabase_url="https://example.supabase.co",
            supabase_publishable_key="publishable-key",
            supabase_secret_key=None,
        )
    )

    assert isinstance(store, SupabaseBrandMemoryStore)
    with pytest.raises(RuntimeError, match="SUPABASE_SECRET_KEY"):
        store.get_memory("test_brand")


def test_auto_memory_store_prefers_supabase_when_configured():
    """Auto mode uses Supabase only when the server-side secret key is configured."""
    store = get_brand_memory_store(
        config=EngineConfig(
            memory_source="auto",
            supabase_url="https://example.supabase.co",
            supabase_publishable_key="anon-key",
            supabase_secret_key="server-secret",
        )
    )
    assert isinstance(store, SupabaseBrandMemoryStore)


def test_auto_memory_store_falls_back_to_file_when_supabase_unconfigured():
    """Auto mode falls back to the file-backed store when Supabase is not configured."""
    store = get_brand_memory_store(
        config=EngineConfig(memory_source="auto", supabase_url=None, supabase_publishable_key=None)
    )
    assert isinstance(store, FileBrandMemoryStore)


def test_auto_memory_store_does_not_treat_publishable_key_as_server_authorization():
    """A public Supabase key alone keeps auto mode on the local store."""
    store = get_brand_memory_store(
        config=EngineConfig(
            memory_source="auto",
            supabase_url="https://example.supabase.co",
            supabase_publishable_key="publishable-key",
            supabase_secret_key=None,
        )
    )
    assert isinstance(store, FileBrandMemoryStore)


def test_brand_memory_model_dump_matches_database_contract():
    """BrandMemory serialization matches the migration schema and PostgREST payload contract."""
    memory = BrandMemory(
        brand_id="brand_contract",
        brand_name="Brand Contract",
        voice_and_tone_preferences=["concise", "technical"],
        approved_terminology=["Brand Contract", "BCT"],
        verified_facts=["Built for enterprise teams"],
        custom_preferences={"priority": "clarity"},
    )
    payload = memory.model_dump(mode="json")

    assert payload["brand_id"] == "brand_contract"
    assert payload["brand_name"] == "Brand Contract"
    assert isinstance(payload["voice_and_tone_preferences"], list)
    assert isinstance(payload["approved_terminology"], list)
    assert isinstance(payload["verified_facts"], list)
    assert isinstance(payload["custom_preferences"], dict)
    assert isinstance(payload["updated_at"], str)
    assert payload["version"] == 1


def test_supabase_brand_memory_store_upserts_on_brand_id_conflict():
    """Remote saves explicitly use the model's brand_id primary key as conflict target."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_client.post.return_value = mock_response

    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )
    memory = BrandMemory(brand_id="brand_upsert", brand_name="Brand Upsert")
    store.save_memory(memory)

    mock_client.post.assert_called_once()
    endpoint, kwargs = mock_client.post.call_args.args[0], mock_client.post.call_args.kwargs
    assert endpoint.endswith("/rest/v1/brand_memory")
    assert kwargs["params"] == {"on_conflict": "brand_id"}
    assert kwargs["headers"]["Prefer"] == "resolution=merge-duplicates,return=minimal"
    assert kwargs["json"]["brand_id"] == "brand_upsert"
    assert kwargs["headers"]["apikey"] == "server-secret"
    assert "Authorization" not in kwargs["headers"]


def test_supabase_brand_memory_store_import_insert_ignores_conflict():
    mock_client = MagicMock()
    mock_response = MagicMock(status_code=201)
    mock_response.json.return_value = [{"brand_id": "brand_import"}]
    mock_client.post.return_value = mock_response
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )

    inserted = store.insert_memory_if_absent(
        BrandMemory(brand_id="brand_import", brand_name="Brand Import")
    )

    assert inserted is True
    kwargs = mock_client.post.call_args.kwargs
    assert kwargs["params"] == {"on_conflict": "brand_id"}
    assert kwargs["headers"]["Prefer"] == "resolution=ignore-duplicates,return=representation"


def test_supabase_brand_memory_store_import_insert_skips_conflict():
    mock_client = MagicMock()
    mock_response = MagicMock(status_code=201)
    mock_response.json.return_value = []
    mock_client.post.return_value = mock_response
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )

    inserted = store.insert_memory_if_absent(
        BrandMemory(brand_id="brand_import", brand_name="Brand Import")
    )

    assert inserted is False


def test_supabase_brand_memory_store_reads_and_validates_payload():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        BrandMemory(
            brand_id="brand_read",
            brand_name="Brand Read",
            version=4,
        ).model_dump(mode="json")
    ]
    mock_client.get.return_value = mock_response
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )

    memory = store.get_memory("brand_read")

    assert memory is not None
    assert memory.brand_id == "brand_read"
    assert memory.version == 4
    assert mock_client.get.call_args.kwargs["params"] == {
        "brand_id": "eq.brand_read",
        "select": "*",
    }


def test_supabase_brand_memory_store_missing_record_returns_none():
    mock_client = MagicMock()
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = []
    mock_client.get.return_value = mock_response
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )

    assert store.get_memory("unknown_brand") is None


def test_supabase_brand_memory_store_update_increments_version():
    mock_client = MagicMock()
    existing = BrandMemory(
        brand_id="brand_update",
        brand_name="Brand Update",
        version=3,
    )
    get_response = MagicMock(status_code=200)
    get_response.json.return_value = [existing.model_dump(mode="json")]
    save_response = MagicMock(status_code=204)
    mock_client.get.return_value = get_response
    mock_client.post.return_value = save_response
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )

    updated = store.update_preferences("brand_update", {"target_audience": "Engineers"})

    assert updated.version == 4
    assert updated.target_audience == "Engineers"
    assert mock_client.post.call_args.kwargs["json"]["version"] == 4


@pytest.mark.parametrize(
    ("records", "expected"),
    [([{"brand_id": "brand_delete"}], True), ([], False)],
)
def test_supabase_brand_memory_store_delete_reports_whether_record_existed(records, expected):
    mock_client = MagicMock()
    response = MagicMock(status_code=200)
    response.json.return_value = records
    mock_client.delete.return_value = response
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )

    assert store.delete_memory("brand_delete") is expected


@pytest.mark.parametrize("status_code", [401, 403])
def test_supabase_memory_store_permission_failures(status_code: int):
    mock_client = MagicMock()
    mock_response = MagicMock(status_code=status_code)
    mock_client.get.return_value = mock_response
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )

    with pytest.raises(PermissionError, match=f"HTTP {status_code}"):
        store.get_memory("brand_read")


def test_supabase_memory_store_missing_table_is_explicit():
    mock_client = MagicMock()
    mock_response = MagicMock(status_code=404, text="PGRST205")
    mock_client.get.return_value = mock_response
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )

    with pytest.raises(RuntimeError, match="migration required"):
        store.get_memory("brand_read")


def test_supabase_memory_store_other_http_error_is_explicit():
    mock_client = MagicMock()
    mock_response = MagicMock(status_code=500, text="database unavailable")
    mock_client.get.return_value = mock_response
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )

    with pytest.raises(RuntimeError, match="HTTP 500"):
        store.get_memory("brand_read")


def test_supabase_memory_store_network_failure_is_explicit():
    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.TimeoutException("timed out")
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )

    with pytest.raises(RuntimeError, match="Failed to connect to Supabase memory store"):
        store.get_memory("brand_read")


def test_supabase_memory_store_invalid_payload_is_rejected():
    mock_client = MagicMock()
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = [{"brand_id": "brand_read"}]
    mock_client.get.return_value = mock_response
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )

    with pytest.raises(RuntimeError, match="failed validation"):
        store.get_memory("brand_read")


def test_supabase_memory_store_invalid_response_json_is_operational_failure():
    mock_client = MagicMock()
    mock_response = MagicMock(status_code=200)
    mock_response.json.side_effect = ValueError("invalid JSON")
    mock_client.get.return_value = mock_response
    store = SupabaseBrandMemoryStore(
        config=EngineConfig(
            supabase_url="https://example.supabase.co",
            supabase_secret_key="server-secret",
        ),
        http_client=mock_client,
    )

    with pytest.raises(RuntimeError, match="invalid JSON"):
        store.get_memory("brand_read")


def test_brand_memory_migrations_revoke_public_access_and_grant_server_role():
    migration_dir = Path(__file__).parents[2] / "supabase" / "migrations"

    # The brand_memory invariants only apply to migrations touching brand_memory.
    # Other tables (e.g. brand_policies) may legitimately define created_at.
    memory_sql = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(migration_dir.glob("*.sql"))
        if "public.brand_memory" in path.read_text(encoding="utf-8").lower()
    )
    assert memory_sql.strip(), "Expected at least one brand_memory migration."
    normalized_sql = " ".join(memory_sql.lower().split())

    for definition in (
        "brand_id text primary key",
        "brand_name text not null",
        "description text",
        "voice_and_tone_preferences jsonb not null default '[]'::jsonb",
        "target_audience text",
        "approved_terminology jsonb not null default '[]'::jsonb",
        "verified_facts jsonb not null default '[]'::jsonb",
        "custom_preferences jsonb not null default '{}'::jsonb",
        "policy_reference text",
        "updated_at timestamptz not null default now()",
        "version integer not null default 1",
    ):
        assert definition in normalized_sql
    assert "'$[*] ? (@.type() != \"string\")'" in normalized_sql
    assert "created_at" not in normalized_sql
    assert "using (true)" not in normalized_sql
    assert "with check (true)" not in normalized_sql
    assert "revoke all privileges on table public.brand_memory from public, anon, authenticated" in normalized_sql
    assert "grant select, insert, update, delete on table public.brand_memory to service_role" in normalized_sql
    assert "grant select, insert, update, delete on table public.brand_memory to anon" not in normalized_sql
    assert "grant select, insert, update, delete on table public.brand_memory to authenticated" not in normalized_sql


def test_existing_access_hardening_migration_is_additive_and_idempotent():
    migration = (
        Path(__file__).parents[2]
        / "supabase"
        / "migrations"
        / "20261023_000002_restrict_brand_memory_access.sql"
    ).read_text(encoding="utf-8").lower()

    assert "alter table public.brand_memory enable row level security" in migration
    assert "drop policy if exists" in migration
    assert "revoke all privileges" in migration
    assert "drop table" not in migration
    assert "delete from" not in migration
    assert "truncate" not in migration


def test_import_brand_memory_dry_run_counts(tmp_path: Path):
    """The importer validates files and reports counts without changing remote state."""
    memory_dir = tmp_path / "brand_memory"
    memory_dir.mkdir()

    valid = BrandMemory(brand_id="dry_run_brand", brand_name="Dry Run Brand")
    (memory_dir / "dry_run_brand.json").write_text(valid.model_dump_json(indent=2), encoding="utf-8")
    (memory_dir / "broken.json").write_text("{not valid json", encoding="utf-8")

    report = import_brand_memory_records(
        source_dir=memory_dir,
        dry_run=True,
        config=EngineConfig(memory_storage_dir=str(memory_dir)),
    )

    assert report["imported"] == 0
    assert report["skipped"] == 1
    assert report["failed"] == 1


def test_import_brand_memory_requires_configured_source_directory(tmp_path: Path):
    other_dir = tmp_path / "other-memory"

    with pytest.raises(ValueError, match="ENGANO_MEMORY_DIR"):
        import_brand_memory_records(
            source_dir=other_dir,
            dry_run=True,
            config=EngineConfig(memory_storage_dir=str(tmp_path / "brand-memory")),
        )


def test_import_brand_memory_refuses_fixture_directories(tmp_path: Path):
    fixture_dir = tmp_path / "data" / "brand_library"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "policy.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="fixture directory"):
        import_brand_memory_records(
            source_dir=fixture_dir,
            dry_run=True,
            config=EngineConfig(memory_storage_dir=str(fixture_dir)),
        )


def test_import_brand_memory_is_idempotent_and_preserves_source(tmp_path: Path, monkeypatch):
    memory_dir = tmp_path / "brand_memory"
    memory_dir.mkdir()
    memory = BrandMemory(brand_id="import_brand", brand_name="Import Brand", version=2)
    source_file = memory_dir / "import_brand.json"
    source_file.write_text(memory.model_dump_json(indent=2), encoding="utf-8")
    original_contents = source_file.read_text(encoding="utf-8")

    class FakeSupabaseStore:
        records = {}
        inserts = 0

        def __init__(self, config):
            pass

        def get_memory(self, brand_id):
            return self.records.get(brand_id)

        def insert_memory_if_absent(self, saved_memory):
            if saved_memory.brand_id in self.records:
                return False
            self.records[saved_memory.brand_id] = saved_memory
            type(self).inserts += 1
            return True

    monkeypatch.setattr("ai_engine.memory.importer.SupabaseBrandMemoryStore", FakeSupabaseStore)
    options = {
        "source_dir": memory_dir,
        "dry_run": False,
        "supabase_url": "https://example.supabase.co",
        "supabase_secret_key": "server-secret",
        "config": EngineConfig(memory_storage_dir=str(memory_dir)),
    }

    first_report = import_brand_memory_records(**options)
    second_report = import_brand_memory_records(**options)

    assert first_report == {"imported": 1, "skipped": 0, "failed": 0}
    assert second_report == {"imported": 0, "skipped": 1, "failed": 0}
    assert FakeSupabaseStore.inserts == 1
    assert source_file.read_text(encoding="utf-8") == original_contents


def test_import_brand_memory_does_not_upsert_when_remote_read_fails(tmp_path: Path, monkeypatch):
    memory_dir = tmp_path / "brand_memory"
    memory_dir.mkdir()
    (memory_dir / "import_brand.json").write_text(
        BrandMemory(brand_id="import_brand", brand_name="Import Brand").model_dump_json(),
        encoding="utf-8",
    )

    class FailingSupabaseStore:
        def __init__(self, config):
            pass

        def get_memory(self, brand_id):
            raise RuntimeError("remote unavailable")

        def insert_memory_if_absent(self, memory):
            pytest.fail("Importer must not upsert after an unsuccessful remote read")

    monkeypatch.setattr("ai_engine.memory.importer.SupabaseBrandMemoryStore", FailingSupabaseStore)
    report = import_brand_memory_records(
        source_dir=memory_dir,
        dry_run=False,
        supabase_url="https://example.supabase.co",
        supabase_secret_key="server-secret",
        config=EngineConfig(memory_storage_dir=str(memory_dir)),
    )

    assert report == {"imported": 0, "skipped": 0, "failed": 1}


def test_import_brand_memory_does_not_overwrite_record_created_after_read(tmp_path: Path, monkeypatch):
    memory_dir = tmp_path / "brand_memory"
    memory_dir.mkdir()
    (memory_dir / "racing_brand.json").write_text(
        BrandMemory(brand_id="racing_brand", brand_name="Racing Brand").model_dump_json(),
        encoding="utf-8",
    )

    class RacingSupabaseStore:
        def __init__(self, config):
            pass

        def get_memory(self, brand_id):
            return None

        def insert_memory_if_absent(self, memory):
            return False

    monkeypatch.setattr("ai_engine.memory.importer.SupabaseBrandMemoryStore", RacingSupabaseStore)
    report = import_brand_memory_records(
        source_dir=memory_dir,
        dry_run=False,
        supabase_url="https://example.supabase.co",
        supabase_secret_key="server-secret",
        config=EngineConfig(memory_storage_dir=str(memory_dir)),
    )

    assert report == {"imported": 0, "skipped": 1, "failed": 0}


def test_backend_brand_memory_api_endpoints(temp_memory_dir: Path, nimbus_policy: BrandPolicy):
    """Backend memory management requires its server-side API key."""
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
    app = create_app(
        review_service=service,
        engine_config=EngineConfig(brand_memory_api_key="backend-test-key"),
        team_store=TeamStore(temp_memory_dir.parent / "team.db"),
    )
    client = TestClient(app)

    assert client.get("/api/brand-memory").status_code == 401
    auth_headers = {"X-Engano-Memory-Key": "backend-test-key"}

    # GET active brand memory
    resp = client.get("/api/brand-memory", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["brand_id"] == "nimbus_cloud"
    assert data["target_audience"] == "Architects"

    # PUT update active brand memory
    put_resp = client.put(
        "/api/brand-memory",
        json={"target_audience": "Senior Executives"},
        headers=auth_headers,
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["target_audience"] == "Senior Executives"
    assert put_resp.json()["version"] == 2

    # GET missing brand returns 404
    missing_resp = client.get("/api/brand-memory/non_existent_brand", headers=auth_headers)
    assert missing_resp.status_code == 404


def test_backend_brand_memory_api_is_disabled_without_server_key(temp_memory_dir: Path, nimbus_policy: BrandPolicy):
    repo = MockPolicyRepository()
    repo.register_policy(nimbus_policy)
    service = ReviewService(
        settings=ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"),
        repository=repo,
        memory_store=FileBrandMemoryStore(storage_dir=temp_memory_dir),
    )
    client = TestClient(
        create_app(
            review_service=service,
            engine_config=EngineConfig(brand_memory_api_key=None),
            team_store=TeamStore(temp_memory_dir.parent / "team.db"),
        )
    )

    assert client.get("/api/brand-memory", headers={"X-Engano-Memory-Key": "unused"}).status_code == 503


def test_backend_brand_memory_api_rejects_wrong_server_key(temp_memory_dir: Path, nimbus_policy: BrandPolicy):
    repo = MockPolicyRepository()
    repo.register_policy(nimbus_policy)
    service = ReviewService(
        settings=ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"),
        repository=repo,
        memory_store=FileBrandMemoryStore(storage_dir=temp_memory_dir),
    )
    client = TestClient(
        create_app(
            review_service=service,
            engine_config=EngineConfig(brand_memory_api_key="backend-test-key"),
            team_store=TeamStore(temp_memory_dir.parent / "team.db"),
        )
    )

    response = client.get(
        "/api/brand-memory",
        headers={"X-Engano-Memory-Key": "wrong-key"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized."


def test_backend_brand_memory_api_does_not_return_storage_error_details(
    tmp_path: Path,
    nimbus_policy: BrandPolicy,
):
    class FailingMemoryStore(FileBrandMemoryStore):
        def get_memory(self, brand_id: str) -> BrandMemory | None:
            raise RuntimeError("remote payload should not be disclosed")

    repo = MockPolicyRepository()
    repo.register_policy(nimbus_policy)
    service = ReviewService(
        settings=ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"),
        repository=repo,
        memory_store=FailingMemoryStore(storage_dir=tmp_path / "brand_memory"),
    )
    client = TestClient(
        create_app(
            review_service=service,
            engine_config=EngineConfig(brand_memory_api_key="backend-test-key"),
            team_store=TeamStore(tmp_path / "team.db"),
        )
    )

    response = client.get(
        "/api/brand-memory",
        headers={"X-Engano-Memory-Key": "backend-test-key"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Brand memory storage unavailable."
    assert "remote payload" not in response.text
