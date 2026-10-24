"""Public review entry point for Engano AI Review Engine.

Provides the stable run_brand_review() interface intended for import by
the FastAPI backend, CLI utilities, and channel integrations:

    from ai_engine.review import run_brand_review
    from ai_engine.schemas import DraftPayload, ReviewInput

    result = run_brand_review(
        DraftPayload(draft_id="1", brand_id="your_brand", content_text="...")
    )
"""

from typing import Optional, Union
from ai_engine.agents.coordinator import CoordinatorAgent
from ai_engine.config import EngineConfig, get_engine_config
from ai_engine.integrations.supabase_policy_repository import (
    BasePolicyRepository,
    SupabasePolicyRepository,
)
from ai_engine.providers.base import BaseProvider
from ai_engine.schemas.brand_memory import BrandMemory
from ai_engine.schemas.payload import DraftPayload
from ai_engine.schemas.review import ReviewInput, ReviewResult


def run_brand_review(
    request: Union[DraftPayload, ReviewInput],
    repository: Optional[BasePolicyRepository] = None,
    config: Optional[EngineConfig] = None,
    provider: Optional[BaseProvider] = None,
    brand_memory: Optional[BrandMemory] = None,
) -> ReviewResult:
    """Execute brand governance review on draft copy.

    Args:
        request: Validated DraftPayload or ReviewInput payload containing draft ID, brand ID,
                 content text, optional images, supplied evidence, and visual metadata.
        repository: Optional policy repository. If omitted, uses production
                    SupabasePolicyRepository configured via environment.
        config: Optional EngineConfig. If omitted, loaded from environment.
        provider: Optional review provider override (rules_only, gemini, ollama).
        brand_memory: Optional persistent BrandMemory context for the active brand.

    Returns:
        ReviewResult containing decision (GREEN, YELLOW, RED), findings,
        safe rewrite proposal, and processing metadata.
    """
    cfg = config or get_engine_config()

    # If no repository provided, initialize production Supabase repository
    repo = repository or SupabasePolicyRepository(config=cfg)

    coordinator = CoordinatorAgent(
        repository=repo,
        config=cfg,
        provider=provider,
        brand_memory=brand_memory,
    )

    return coordinator.run_review(request)
