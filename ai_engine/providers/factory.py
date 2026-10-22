"""Provider factory for Engano AI Review Engine.

Instantiates and configures review providers: rules_only, gemini, ollama, or auto.
Ensures rules_only never connects to external services and local-only never leaks
data to cloud providers.
"""

import logging
from typing import Optional
import httpx
from ai_engine.config import EngineConfig, ProviderType, get_engine_config
from ai_engine.providers.base import BaseProvider, ProviderResponse
from ai_engine.providers.gemini import GeminiProvider
from ai_engine.providers.ollama import OllamaProvider
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import Finding

logger = logging.getLogger(__name__)


class RulesOnlyProvider(BaseProvider):
    """Deterministic-only provider that performs no LLM or network operations."""

    def review(
        self,
        content_text: str,
        policy: BrandPolicy,
        deterministic_findings: list[Finding],
    ) -> ProviderResponse:
        """Return empty semantic findings; deterministic rules handle evaluation."""
        return ProviderResponse(
            provider_name="rules_only",
            findings=[],
            raw_response=None,
            latency_ms=0.0,
        )


def _is_ollama_reachable(base_url: str, timeout: float = 2.0) -> bool:
    """Check if local Ollama daemon is reachable without hanging."""
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def get_provider(
    provider_type: Optional[str | ProviderType] = None,
    config: Optional[EngineConfig] = None,
) -> BaseProvider:
    """Create review provider according to configuration or explicit override."""
    cfg = config or get_engine_config()
    target_type = ProviderType(provider_type) if provider_type else cfg.ai_provider

    if target_type == ProviderType.RULES_ONLY:
        return RulesOnlyProvider()

    elif target_type == ProviderType.OLLAMA:
        return OllamaProvider(config=cfg)

    elif target_type == ProviderType.GEMINI:
        return GeminiProvider(config=cfg)

    elif target_type == ProviderType.AUTO:
        # Documented auto behavior:
        # 1. Prefer local Ollama if running
        # 2. Otherwise prefer Gemini if API key is configured
        # 3. Otherwise fall back to rules_only
        if _is_ollama_reachable(cfg.ollama_base_url):
            logger.info("Auto provider selected local Ollama (service active)")
            return OllamaProvider(config=cfg)

        if cfg.gemini_api_key and cfg.gemini_api_key.get_secret_value().strip():
            logger.info("Auto provider selected Gemini (API key configured)")
            return GeminiProvider(config=cfg)

        logger.info("Auto provider falling back to rules_only")
        return RulesOnlyProvider()

    else:
        raise ValueError(f"Unsupported provider type '{target_type}'.")
