"""Shared bridge from every channel (Discord, WhatsApp, ...) to ai_engine."""

import asyncio
import logging
import os
from dataclasses import dataclass

from ai_engine import run_brand_review
from ai_engine.integrations import (
    BasePolicyRepository,
    MockPolicyRepository,
    SupabasePolicyRepository,
)
from ai_engine.schemas.review import ReviewInput, ReviewResult

from .env import REPO_ROOT, ROOT_ENV

log = logging.getLogger("engano.review")

FIXTURE_DIR = REPO_ROOT / "data" / "brand_library"
POLICY_SOURCES = ("supabase", "fixture")


@dataclass(frozen=True)
class ReviewSettings:
    # Brand every channel draft is checked against (one brand for now).
    brand_id: str
    # Where brand policies come from: "supabase" (production) or "fixture"
    # (data/brand_library/*.json, local testing only). Never chosen implicitly.
    policy_source: str

    @classmethod
    def from_env(cls) -> "ReviewSettings":
        brand_id = os.getenv("ENGANO_BRAND_ID")
        if not brand_id:
            raise SystemExit(f"ENGANO_BRAND_ID is missing. Add it to {ROOT_ENV}")
        policy_source = os.getenv("ENGANO_POLICY_SOURCE", "supabase").strip().lower()
        if policy_source not in POLICY_SOURCES:
            raise SystemExit(
                f"ENGANO_POLICY_SOURCE must be one of {POLICY_SOURCES}, got {policy_source!r}"
            )
        return cls(brand_id=brand_id, policy_source=policy_source)


def make_repository(settings: ReviewSettings) -> BasePolicyRepository:
    if settings.policy_source == "fixture":
        repo = MockPolicyRepository()
        for path in sorted(FIXTURE_DIR.glob("*.json")):
            policy = repo.load_fixture(path)
            log.info("Loaded test fixture brand %s from %s", policy.brand_id, path.name)
        log.warning("Using local test fixtures as the policy source. Not for production.")
        return repo
    return SupabasePolicyRepository()


class ReviewService:
    def __init__(self, settings: ReviewSettings, repository: BasePolicyRepository | None = None):
        self.settings = settings
        self.repository = repository or make_repository(settings)

    async def review_text(self, draft_id: str, text: str) -> ReviewResult:
        request = ReviewInput(draft_id=draft_id, brand_id=self.settings.brand_id, content_text=text)
        # run_brand_review is synchronous (and may call an LLM), so keep it off the event loop.
        return await asyncio.to_thread(run_brand_review, request, self.repository)
