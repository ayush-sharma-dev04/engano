"""RAG: chunking, isolation, retrieval, and coordinator wiring (no network)."""

import hashlib
from typing import List

from ai_engine.agents.coordinator import CoordinatorAgent
from ai_engine.config import EngineConfig
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.providers.base import BaseProvider, ProviderResponse
from ai_engine.rag import InMemoryChunkStore, Retriever, chunk_memory, chunk_policy
from ai_engine.rag.embedder import BaseEmbedder
from ai_engine.schemas.brand_memory import BrandMemory
from ai_engine.schemas.review import ReviewInput

FIXTURE = "data/brand_library/nimbus_db.json"


class WordEmbedder(BaseEmbedder):
    """Deterministic bag-of-words hashing embedder."""

    def _vec(self, text: str) -> List[float]:
        v = [0.0] * 64
        for w in text.lower().replace("%", " ").replace(".", " ").split():
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1.0
        return v

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


def _policy():
    repo = MockPolicyRepository()
    return repo, repo.load_fixture(FIXTURE)


def test_chunk_policy_one_chunk_per_rule_with_ids():
    _, policy = _policy()
    ids = {(c.source, c.source_id) for c in chunk_policy(policy)}
    assert ("fact", "fact_sla_uptime") in ids
    assert ("offer", "offer_free_forever") in ids
    assert ("legal", "legal_disclaimer_sla") in ids


def test_chunk_memory_none_is_empty_and_memory_is_chunked():
    assert chunk_memory(None) == []
    mem = BrandMemory(brand_id="b", brand_name="B", voice_and_tone_preferences=["calm"], verified_facts=["x"])
    assert {c.source_id for c in chunk_memory(mem)} == {"voice", "fact_0"}


def test_retrieves_relevant_rule_and_isolates_brands():
    _, policy = _policy()
    store = InMemoryChunkStore()
    r = Retriever(WordEmbedder(), store, top_k=2)
    r.index_brand(policy)
    other = policy.model_copy(update={"brand_id": "other_brand", "factual_rules": [], "offers": []})
    r.index_brand(other)

    hits = r.retrieve("nimbus_cloud", "we promise 100% uptime SLA monthly")
    assert any("fact_sla_uptime" in h for h in hits)
    assert all("[offer:" not in h for h in r.retrieve("other_brand", "free forever offer"))


def test_empty_draft_retrieves_nothing():
    assert Retriever(WordEmbedder(), InMemoryChunkStore()).retrieve("b", "  ") == []


class CapturingProvider(BaseProvider):
    provider_name = "capture"

    def __init__(self):
        self.context = "unset"

    def review(self, content_text, policy, deterministic_findings, images=None, context=None):
        self.context = context
        return ProviderResponse(provider_name="capture")


class BoomRetriever:
    def retrieve(self, brand_id, text):
        raise RuntimeError("db down")


def _run(retriever):
    repo, policy = _policy()
    provider = CapturingProvider()
    agent = CoordinatorAgent(repo, config=EngineConfig(), provider=provider, retriever=retriever)
    result = agent.run_review(ReviewInput(draft_id="d", brand_id="nimbus_cloud", content_text="100% uptime always").to_payload()
                              if hasattr(ReviewInput, "to_payload") else ReviewInput(draft_id="d", brand_id="nimbus_cloud", content_text="100% uptime always"))
    return provider, result


def test_coordinator_passes_retrieved_context_to_provider():
    _, policy = _policy()
    store = InMemoryChunkStore()
    r = Retriever(WordEmbedder(), store)
    r.index_brand(policy)
    provider, result = _run(r)
    assert provider.context and any("fact_sla_uptime" in c for c in provider.context)
    assert "RAGRetriever" in result.metadata.agents_executed


def test_retrieval_failure_never_breaks_review():
    provider, result = _run(BoomRetriever())
    assert provider.context is None
    assert result.completion_status == "completed"
