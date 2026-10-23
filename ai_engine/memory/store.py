"""Brand Memory Storage Layer.

Provides persistent, reusable brand context storage across sessions:
- BaseBrandMemoryStore: Abstract interface
- FileBrandMemoryStore: Durable filesystem storage (survives backend restarts)
- SupabaseBrandMemoryStore: Supabase PostgreSQL storage boundary
- get_brand_memory_store: Factory resolver
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import threading
from typing import Any, Dict, Optional
import httpx
from ai_engine.config import EngineConfig, get_engine_config
from ai_engine.schemas.brand_memory import BrandMemory

logger = logging.getLogger(__name__)


class BaseBrandMemoryStore(ABC):
    """Abstract interface for brand memory persistence."""

    @abstractmethod
    def get_memory(self, brand_id: str) -> Optional[BrandMemory]:
        """Retrieve brand memory for brand_id. Returns None if not found."""
        pass

    @abstractmethod
    def save_memory(self, memory: BrandMemory) -> None:
        """Persist or overwrite brand memory record."""
        pass

    @abstractmethod
    def update_preferences(self, brand_id: str, updates: Dict[str, Any]) -> BrandMemory:
        """Apply deliberate updates to brand memory preferences."""
        pass

    @abstractmethod
    def delete_memory(self, brand_id: str) -> bool:
        """Delete brand memory record. Returns True if deleted, False if not found."""
        pass


class FileBrandMemoryStore(BaseBrandMemoryStore):
    """Persistent filesystem brand memory store.

    Stores brand memory records as validated JSON files.
    Survives backend restarts and process reloads.
    Enforces brand isolation and atomic writes.
    """

    def __init__(self, storage_dir: str | Path = "data/brand_memory") -> None:
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _file_path(self, brand_id: str) -> Path:
        clean_id = brand_id.strip().lower()
        if not clean_id or "/" in clean_id or ".." in clean_id:
            raise ValueError(f"Invalid brand_id '{brand_id}' for file storage.")
        return self.storage_dir / f"{clean_id}.json"

    def get_memory(self, brand_id: str) -> Optional[BrandMemory]:
        """Load persistent brand memory from disk."""
        path = self._file_path(brand_id)
        if not path.exists():
            return None

        with self._lock:
            try:
                raw_text = path.read_text(encoding="utf-8")
                data = json.loads(raw_text)
                return BrandMemory.model_validate(data)
            except json.JSONDecodeError as exc:
                logger.error("Corrupted brand memory JSON at %s: %s", path, exc)
                raise ValueError(f"Corrupted brand memory record for '{brand_id}': {exc}") from exc
            except Exception as exc:
                logger.error("Failed to load brand memory for '%s': %s", brand_id, exc)
                raise ValueError(f"Failed to validate brand memory for '{brand_id}': {exc}") from exc

    def save_memory(self, memory: BrandMemory) -> None:
        """Persist brand memory record atomically to disk."""
        path = self._file_path(memory.brand_id)
        temp_path = path.with_suffix(".tmp")
        payload = memory.model_dump_json(indent=2)

        with self._lock:
            try:
                temp_path.write_text(payload, encoding="utf-8")
                temp_path.replace(path)
                logger.info("Persisted brand memory for '%s' to %s", memory.brand_id, path)
            except Exception as exc:
                if temp_path.exists():
                    temp_path.unlink()
                raise RuntimeError(f"Failed to persist brand memory for '{memory.brand_id}': {exc}") from exc

    def update_preferences(self, brand_id: str, updates: Dict[str, Any]) -> BrandMemory:
        """Apply updates to brand preferences and persist them."""
        current = self.get_memory(brand_id)
        if not current:
            raise KeyError(f"Brand memory for '{brand_id}' does not exist.")

        allowed_fields = {
            "brand_name",
            "description",
            "voice_and_tone_preferences",
            "target_audience",
            "approved_terminology",
            "verified_facts",
            "custom_preferences",
            "policy_reference",
        }

        current_dict = current.model_dump()
        for k, v in updates.items():
            if k in allowed_fields:
                current_dict[k] = v

        current_dict["version"] = current.version + 1
        current_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

        updated_memory = BrandMemory.model_validate(current_dict)
        self.save_memory(updated_memory)
        return updated_memory

    def delete_memory(self, brand_id: str) -> bool:
        """Delete brand memory file."""
        path = self._file_path(brand_id)
        with self._lock:
            if path.exists():
                path.unlink()
                return True
            return False


class SupabaseBrandMemoryStore(BaseBrandMemoryStore):
    """Production Supabase PostgreSQL brand memory store boundary."""

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

    def _get_headers(self) -> Dict[str, str]:
        if not self.supabase_url or not self.publishable_key:
            raise RuntimeError(
                "Supabase brand memory storage unconfigured. SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are required."
            )
        return {
            "apikey": self.publishable_key,
            "Authorization": f"Bearer {self.publishable_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_memory(self, brand_id: str) -> Optional[BrandMemory]:
        headers = self._get_headers()
        endpoint = f"{self.supabase_url.rstrip('/')}/rest/v1/brand_memory"
        params = {"brand_id": f"eq.{brand_id}", "select": "*"}

        try:
            resp = self._client.get(endpoint, headers=headers, params=params)
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to Supabase memory store: {exc}") from exc

        if resp.status_code == 404:
            raise RuntimeError(
                "Supabase 'brand_memory' table does not exist in schema cache. Database migration required."
            )
        if resp.status_code in (401, 403):
            raise PermissionError(f"Supabase permission denied (HTTP {resp.status_code})")
        if resp.status_code != 200:
            raise RuntimeError(f"Supabase returned HTTP {resp.status_code}: {resp.text}")

        records = resp.json()
        if not records:
            return None
        return BrandMemory.model_validate(records[0])

    def save_memory(self, memory: BrandMemory) -> None:
        headers = self._get_headers()
        headers["Prefer"] = "resolution=merge-duplicates"
        endpoint = f"{self.supabase_url.rstrip('/')}/rest/v1/brand_memory"

        try:
            resp = self._client.post(endpoint, headers=headers, json=memory.model_dump())
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to Supabase memory store: {exc}") from exc

        if resp.status_code == 404:
            raise RuntimeError(
                "Supabase 'brand_memory' table does not exist in schema cache. Database migration required."
            )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to save brand memory to Supabase: HTTP {resp.status_code}: {resp.text}")

    def update_preferences(self, brand_id: str, updates: Dict[str, Any]) -> BrandMemory:
        current = self.get_memory(brand_id)
        if not current:
            raise KeyError(f"Brand memory for '{brand_id}' does not exist.")

        allowed_fields = {
            "brand_name",
            "description",
            "voice_and_tone_preferences",
            "target_audience",
            "approved_terminology",
            "verified_facts",
            "custom_preferences",
            "policy_reference",
        }

        current_dict = current.model_dump()
        for k, v in updates.items():
            if k in allowed_fields:
                current_dict[k] = v

        current_dict["version"] = current.version + 1
        current_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

        updated = BrandMemory.model_validate(current_dict)
        self.save_memory(updated)
        return updated

    def delete_memory(self, brand_id: str) -> bool:
        headers = self._get_headers()
        endpoint = f"{self.supabase_url.rstrip('/')}/rest/v1/brand_memory"
        params = {"brand_id": f"eq.{brand_id}"}
        resp = self._client.delete(endpoint, headers=headers, params=params)
        return resp.status_code in (200, 204)


def get_brand_memory_store(config: Optional[EngineConfig] = None) -> BaseBrandMemoryStore:
    """Resolve configured brand memory store."""
    cfg = config or get_engine_config()
    source = os.getenv("ENGANO_MEMORY_SOURCE", cfg.memory_source).strip().lower()

    if source == "supabase":
        return SupabaseBrandMemoryStore(config=cfg)
    return FileBrandMemoryStore(storage_dir=cfg.memory_storage_dir)
