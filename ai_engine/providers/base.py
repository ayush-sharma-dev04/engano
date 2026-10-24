"""Base semantic review provider interface.

Defines the contract for LLM-backed review providers (Gemini, Ollama, and RulesOnly).
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional
from pydantic import BaseModel, Field
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import Finding
from ai_engine.schemas.payload import ImageItem


class ProviderResponse(BaseModel):
    """Normalized response returned by an AI review provider."""
    provider_name: str
    findings: List[Finding] = Field(default_factory=list)
    raw_response: Optional[str] = None
    latency_ms: float = 0.0


class BaseProvider(ABC):
    """Abstract base class for all review providers."""

    provider_name: str = "base"

    @abstractmethod
    def review(
        self,
        content_text: str,
        policy: BrandPolicy,
        deterministic_findings: List[Finding],
        images: Optional[List[ImageItem]] = None,
        context: Optional[List[str]] = None,
    ) -> ProviderResponse:
        """Perform semantic review of draft content against authoritative policy.

        `images` carries visual assets (URLs or embedded bytes) from the channel
        payload so that multimodal providers (e.g. qwen2.5vl) can inspect imagery.
        """
        pass

    def generate_rewrite(
        self,
        content_text: str,
        policy: BrandPolicy,
        findings: List[Finding],
        images: Optional[List[ImageItem]] = None,
    ) -> Optional[str]:
        """Generate a coherent rewrite of the draft via the LLM.

        Returns the rewritten text, or None when the provider cannot produce one
        (so RewriteAgent falls back to deterministic mechanical fixes).
        The base implementation is a no-op; rules-only and non-LLM providers need
        not override.
        """
        return None
