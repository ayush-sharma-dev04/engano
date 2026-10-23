"""Base semantic review provider interface.

Defines the contract for LLM-backed review providers (Gemini, Ollama, and RulesOnly).
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import Finding


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
    ) -> ProviderResponse:
        """Perform semantic review of draft content against authoritative policy."""
        pass
