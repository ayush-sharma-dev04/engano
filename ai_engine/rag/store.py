"""Chunk storage: Supabase pgvector in production, in-memory for tests."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ai_engine.config import EngineConfig, get_engine_config
from ai_engine.rag.chunker import Chunk


class RetrievedChunk(Chunk):
    similarity: float = 0.0


class BaseChunkStore(ABC):
    @abstractmethod
    def replace_brand(self, brand_id: str, chunks: List[Chunk], embeddings: List[List[float]]) -> int:
        """Replace all chunks of one brand. Returns the number stored."""

    @abstractmethod
    def search(self, brand_id: str, query_embedding: List[float], top_k: int) -> List[RetrievedChunk]: ...


class InMemoryChunkStore(BaseChunkStore):
    def __init__(self) -> None:
        self._rows: Dict[str, List[Tuple[Chunk, List[float]]]] = {}

    def replace_brand(self, brand_id: str, chunks: List[Chunk], embeddings: List[List[float]]) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        self._rows[brand_id] = list(zip(chunks, embeddings))
        return len(chunks)

    def search(self, brand_id: str, query_embedding: List[float], top_k: int) -> List[RetrievedChunk]:
        def cos(a: List[float], b: List[float]) -> float:
            na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
            return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0

        scored = sorted(
            ((cos(query_embedding, emb), c) for c, emb in self._rows.get(brand_id, [])),
            key=lambda t: t[0],
            reverse=True,
        )
        return [RetrievedChunk(**c.model_dump(), similarity=s) for s, c in scored[:top_k]]


class SupabaseChunkStore(BaseChunkStore):
    """Talks to PostgREST with the backend-only secret key (tables are service_role only)."""

    def __init__(self, config: Optional[EngineConfig] = None, http_client: Optional[httpx.Client] = None) -> None:
        cfg = config or get_engine_config()
        self.url = (cfg.supabase_url or "").rstrip("/")
        self.key = cfg.supabase_secret_key.get_secret_value().strip() if cfg.supabase_secret_key else ""
        self._client = http_client or httpx.Client(timeout=cfg.request_timeout_seconds)

    def _headers(self, **extra: str) -> Dict[str, str]:
        if not self.url or not self.key:
            raise RuntimeError("Supabase RAG store unconfigured. SUPABASE_URL and SUPABASE_SECRET_KEY are required.")
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json", **extra}

    @staticmethod
    def _check(resp: httpx.Response, op: str) -> None:
        if resp.status_code == 404:
            raise RuntimeError(f"Supabase RAG {op}: table/function missing. Apply migration 20261024_000003.")
        if resp.status_code in (401, 403):
            raise PermissionError(f"Supabase RAG {op}: permission denied (HTTP {resp.status_code})")
        if resp.status_code >= 300:
            raise RuntimeError(f"Supabase RAG {op} returned HTTP {resp.status_code}")

    def replace_brand(self, brand_id: str, chunks: List[Chunk], embeddings: List[List[float]]) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        rows: List[Dict[str, Any]] = [
            {**c.model_dump(), "embedding": "[" + ",".join(f"{x:.7f}" for x in e) + "]"}
            for c, e in zip(chunks, embeddings)
        ]
        # Upsert first, then delete stale rows, so a failed run never leaves the brand empty.
        if rows:
            resp = self._client.post(
                f"{self.url}/rest/v1/brand_chunks",
                headers=self._headers(Prefer="resolution=merge-duplicates,return=minimal"),
                params={"on_conflict": "brand_id,source,source_id"},
                json=rows,
            )
            self._check(resp, "upsert")
        keep = {(c.source, c.source_id) for c in chunks}
        existing = self._client.get(
            f"{self.url}/rest/v1/brand_chunks",
            headers=self._headers(),
            params={"brand_id": f"eq.{brand_id}", "select": "id,source,source_id"},
        )
        self._check(existing, "list")
        stale = [r["id"] for r in existing.json() if (r["source"], r["source_id"]) not in keep]
        for rid in stale:
            self._check(
                self._client.delete(f"{self.url}/rest/v1/brand_chunks", headers=self._headers(), params={"id": f"eq.{rid}"}),
                "delete",
            )
        return len(rows)

    def search(self, brand_id: str, query_embedding: List[float], top_k: int) -> List[RetrievedChunk]:
        resp = self._client.post(
            f"{self.url}/rest/v1/rpc/match_brand_chunks",
            headers=self._headers(),
            json={
                "p_brand_id": brand_id,
                "p_query_embedding": "[" + ",".join(f"{x:.7f}" for x in query_embedding) + "]",
                "p_match_count": top_k,
            },
        )
        self._check(resp, "search")
        return [
            RetrievedChunk(
                brand_id=brand_id,
                source=r["source"],
                source_id=r["source_id"],
                content=r["content"],
                metadata=r.get("metadata") or {},
                similarity=float(r["similarity"]),
            )
            for r in resp.json()
        ]
