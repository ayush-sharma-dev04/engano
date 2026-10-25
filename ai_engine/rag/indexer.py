"""CLI: embed a brand's policy (and memory) into Supabase.

    python -m ai_engine.rag.indexer --brand nimbus_cloud            # dry run
    python -m ai_engine.rag.indexer --brand nimbus_cloud --apply
"""

from __future__ import annotations

import argparse
import json
from typing import Optional

from ai_engine.config import get_engine_config
from ai_engine.integrations.supabase_policy_repository import (
    MockPolicyRepository,
    SupabasePolicyRepository,
)
from ai_engine.memory.store import get_brand_memory_store
from ai_engine.rag.chunker import chunk_memory, chunk_policy
from ai_engine.rag.retriever import Retriever
from ai_engine.rag.embedder import GeminiEmbedder
from ai_engine.rag.store import SupabaseChunkStore


def main(argv: Optional[list[str]] = None) -> None:
    p = argparse.ArgumentParser(description="Index brand policy + memory for RAG")
    p.add_argument("--brand", required=True)
    p.add_argument("--source", choices=["fixture", "supabase"], default="fixture")
    p.add_argument("--fixture", default="data/brand_library/nimbus_db.json")
    p.add_argument("--apply", action="store_true", help="Embed and write to Supabase (default: dry run)")
    args = p.parse_args(argv)

    cfg = get_engine_config()
    if args.source == "fixture":
        repo = MockPolicyRepository()
        repo.load_fixture(args.fixture)
    else:
        repo = SupabasePolicyRepository(config=cfg)
    policy = repo.get_policy(args.brand)
    if policy is None:
        raise SystemExit(f"No policy found for '{args.brand}'.")
    try:
        memory = get_brand_memory_store(cfg).get_memory(args.brand)
    except Exception:
        memory = None

    chunks = chunk_policy(policy) + chunk_memory(memory)
    report = {"brand": args.brand, "chunks": len(chunks), "sources": sorted({c.source for c in chunks}), "applied": False}
    if args.apply:
        report["stored"] = Retriever(GeminiEmbedder(cfg), SupabaseChunkStore(cfg)).index_brand(policy, memory)
        report["applied"] = True
    print(json.dumps(report))


if __name__ == "__main__":
    main()
