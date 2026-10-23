"""Import durable JSON-backed brand memory records into Supabase."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, Optional

from pydantic import ValidationError

from ai_engine.config import EngineConfig, get_engine_config
from ai_engine.memory.store import SupabaseBrandMemoryStore
from ai_engine.schemas.brand_memory import BrandMemory


def iter_brand_memory_files(source_dir: str | Path) -> Iterable[Path]:
    """Yield data files from a configured memory directory, rejecting known fixture roots."""
    directory = Path(source_dir).resolve()
    if {"brand_library", "fixtures", "test_fixtures"}.intersection(
        part.lower() for part in directory.parts
    ):
        raise ValueError("Refusing to import a policy fixture or test-fixture directory.")
    if not directory.exists():
        return []
    return sorted(path for path in directory.glob("*.json") if path.is_file())


def import_brand_memory_records(
    source_dir: str | Path | None = None,
    *,
    dry_run: bool = True,
    supabase_url: Optional[str] = None,
    supabase_secret_key: Optional[str] = None,
    config: Optional[EngineConfig] = None,
) -> Dict[str, int]:
    """Validate local records and optionally insert only brands absent from Supabase.

    Existing remote records are always skipped. Missing records use an atomic
    insert-if-absent operation, so concurrent remote writes are never overwritten.
    """
    cfg = config or get_engine_config()
    directory = Path(source_dir or cfg.memory_storage_dir).resolve()
    configured_directory = Path(cfg.memory_storage_dir).resolve()
    if directory != configured_directory:
        raise ValueError("Source directory must match the configured ENGANO_MEMORY_DIR.")

    report: Dict[str, int] = {"imported": 0, "skipped": 0, "failed": 0}
    if not directory.exists():
        return report

    effective_url = supabase_url or cfg.supabase_url
    effective_secret_key = supabase_secret_key or (
        cfg.supabase_secret_key.get_secret_value() if cfg.supabase_secret_key else None
    )
    remote_store = None
    if effective_url and effective_secret_key:
        remote_store = SupabaseBrandMemoryStore(
            config=EngineConfig(
                supabase_url=effective_url,
                supabase_secret_key=effective_secret_key,
                memory_source="supabase",
            )
        )

    for file_path in iter_brand_memory_files(directory):
        try:
            memory = BrandMemory.model_validate(
                json.loads(file_path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, ValidationError):
            report["failed"] += 1
            continue

        if file_path.stem != memory.brand_id:
            report["failed"] += 1
            continue

        if remote_store is None:
            report["skipped" if dry_run else "failed"] += 1
            continue

        try:
            remote = remote_store.get_memory(memory.brand_id)
        except (PermissionError, RuntimeError, ValueError):
            report["failed"] += 1
            continue

        if remote is not None or dry_run:
            report["skipped"] += 1
            continue

        try:
            if remote_store.insert_memory_if_absent(memory):
                report["imported"] += 1
            else:
                report["skipped"] += 1
        except (PermissionError, RuntimeError, ValueError):
            report["failed"] += 1

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run or apply JSON-backed brand memory to Supabase")
    parser.add_argument("--source-dir", default=None, help="Configured memory directory (defaults to ENGANO_MEMORY_DIR)")
    parser.add_argument("--apply", action="store_true", help="Persist absent memories to Supabase instead of dry-running")
    parser.add_argument("--supabase-url", default=None, help="Override SUPABASE_URL for the import")
    args = parser.parse_args()

    report = import_brand_memory_records(
        source_dir=args.source_dir,
        dry_run=not args.apply,
        supabase_url=args.supabase_url,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
