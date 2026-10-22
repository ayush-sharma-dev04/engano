"""Bridge between the Discord bot and ai_engine."""

import asyncio
import logging

from ai_engine import run_brand_review
from ai_engine.integrations import (
    BasePolicyRepository,
    MockPolicyRepository,
    SupabasePolicyRepository,
)
from ai_engine.schemas.review import ReviewInput, ReviewResult

from .config import REPO_ROOT, Settings

log = logging.getLogger("engano.discord")

FIXTURE_DIR = REPO_ROOT / "data" / "brand_library"


def make_repository(settings: Settings) -> BasePolicyRepository:
    if settings.policy_source == "fixture":
        repo = MockPolicyRepository()
        for path in sorted(FIXTURE_DIR.glob("*.json")):
            policy = repo.load_fixture(path)
            log.info("Loaded test fixture brand %s from %s", policy.brand_id, path.name)
        log.warning("Using local test fixtures as the policy source. Not for production.")
        return repo
    return SupabasePolicyRepository()


async def review(request: ReviewInput, repository: BasePolicyRepository) -> ReviewResult:
    # run_brand_review is synchronous (and may call an LLM), so keep it off the event loop.
    return await asyncio.to_thread(run_brand_review, request, repository)
