"""Index a brand and retrieve cited context for a draft."""

from __future__ import annotations

import logging
from typing import List, Optional

from ai_engine.config import EngineConfig, get_engine_config
from ai_engine.rag.chunker import chunk_memory, chunk_policy
from ai_engine.rag.embedder import BaseEmbedder, GeminiEmbedder
from ai_engine.rag.store import BaseChunkStore, SupabaseChunkStore
from ai_engine.schemas.brand_memory import BrandMemory
from ai_engine.schemas.brand_policy import BrandPolicy

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(self, embedder: BaseEmbedder, store: BaseChunkStore, top_k: int = 6) -> None:
        self.embedder = embedder
        self.store = store
        self.top_k = top_k

    def index_brand(self, policy: BrandPolicy, memory: Optional[BrandMemory] = None) -> int:
        chunks = chunk_policy(policy) + chunk_memory(memory)
        embeddings = self.embedder.embed_documents([c.content for c in chunks])
        return self.store.replace_brand(policy.brand_id, chunks, embeddings)

    def retrieve(self, brand_id: str, draft_text: str) -> List[str]:
        """Return context lines like '[fact:fact_sla_uptime] Approved fact ...'."""
        if not draft_text.strip():
            return []
        hits = self.store.search(brand_id, self.embedder.embed_query(draft_text), self.top_k)
        return [f"[{h.source}:{h.source_id}] {h.content}" for h in hits]


def get_retriever(config: Optional[EngineConfig] = None) -> Optional[Retriever]:
    """Retriever when ENGANO_RAG_ENABLED and Supabase + Gemini are configured, else None."""
    cfg = config or get_engine_config()
    if not cfg.rag_enabled:
        return None
    try:
        return Retriever(GeminiEmbedder(cfg), SupabaseChunkStore(cfg), cfg.rag_top_k)
    except Exception as exc:
        logger.warning("RAG disabled: %s", exc)
        return None
