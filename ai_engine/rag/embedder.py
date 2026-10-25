"""Text embedding providers. Dimension must match the pgvector column (768)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from ai_engine.config import EngineConfig, get_engine_config

EMBEDDING_DIMS = 768


class BaseEmbedder(ABC):
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> List[float]: ...


class GeminiEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[EngineConfig] = None, client: Optional[Any] = None) -> None:
        self.config = config or get_engine_config()
        self.model = self.config.embedding_model
        if client is not None:
            self._client = client
        else:
            from google import genai

            if not self.config.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is required for embeddings.")
            self._client = genai.Client(api_key=self.config.gemini_api_key.get_secret_value())

    def _embed(self, texts: List[str], task_type: str) -> List[List[float]]:
        from google.genai import types

        if not texts:
            return []
        resp = self._client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIMS),
        )
        vectors = [list(e.values) for e in resp.embeddings]
        if len(vectors) != len(texts) or any(len(v) != EMBEDDING_DIMS for v in vectors):
            raise RuntimeError("Embedding response has unexpected shape.")
        return vectors

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> List[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]
