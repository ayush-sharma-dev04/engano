"""Retrieval-augmented context for semantic review.

Brand policy and memory are chunked, embedded and stored per brand. At review
time the most relevant chunks are retrieved and handed to the LLM as cited,
advisory context. The BrandPolicy itself stays authoritative.
"""

from ai_engine.rag.chunker import Chunk, chunk_memory, chunk_policy
from ai_engine.rag.embedder import BaseEmbedder, GeminiEmbedder
from ai_engine.rag.retriever import Retriever, get_retriever
from ai_engine.rag.store import BaseChunkStore, InMemoryChunkStore, SupabaseChunkStore

__all__ = [
    "BaseChunkStore",
    "BaseEmbedder",
    "Chunk",
    "GeminiEmbedder",
    "InMemoryChunkStore",
    "Retriever",
    "SupabaseChunkStore",
    "chunk_memory",
    "chunk_policy",
    "get_retriever",
]
