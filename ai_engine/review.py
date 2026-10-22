"""Public review entry point for Engano AI Review Engine.

Provides the stable run_brand_review() interface intended for import by
the FastAPI backend or CLI utilities:

    from ai_engine.review import run_brand_review
    from ai_engine.schemas import ReviewInput

    result = run_brand_review(ReviewInput(draft_id="1", brand_id="nimbus", content_text="..."))
"""

from typing import Optional
from ai_engine.agents.orchestrator import ReviewOrchestrator
from ai_engine.config import EngineConfig, get_engine_config
from ai_engine.integrations.supabase_policy_repository import (
    BasePolicyRepository,
    SupabasePolicyRepository,
)
from ai_engine.providers.base import BaseProvider
from ai_engine.schemas.review import ReviewInput, ReviewResult


def run_brand_review(
    request: ReviewInput,
    repository: Optional[BasePolicyRepository] = None,
    config: Optional[EngineConfig] = None,
    provider: Optional[BaseProvider] = None,
) -> ReviewResult:
    """Execute brand governance review on draft copy.

    Args:
        request: Validated ReviewInput payload containing draft ID, brand ID, text,
                 optional supplied evidence, and optional visual metadata.
        repository: Optional policy repository. If omitted, uses production
                    SupabasePolicyRepository configured via environment.
        config: Optional EngineConfig. If omitted, loaded from environment.
        provider: Optional review provider override (rules_only, gemini, ollama).

    Returns:
        ReviewResult containing decision (GREEN, YELLOW, RED), findings,
        safe rewrite proposal, and processing metadata.
    """
    cfg = config or get_engine_config()

    # If no repository provided, initialize production Supabase repository
    repo = repository or SupabasePolicyRepository(config=cfg)

    orchestrator = ReviewOrchestrator(
        repository=repo,
        config=cfg,
        provider=provider,
    )

    return orchestrator.run_review(request)
