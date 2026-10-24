"""Shared bridge from every channel (Discord, WhatsApp, ...) to ai_engine."""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ai_engine import run_brand_review
from ai_engine.adapters import get_adapter
from ai_engine.integrations import (
    BasePolicyRepository,
    MockPolicyRepository,
    SupabasePolicyRepository,
)
from ai_engine.memory.store import (
    BaseBrandMemoryStore,
    get_brand_memory_store,
)
from ai_engine.schemas.brand_memory import BrandMemory
from ai_engine.schemas.payload import DraftPayload
from ai_engine.schemas.review import ReviewDecision, ReviewInput, ReviewResult

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
    def __init__(
        self,
        settings: ReviewSettings,
        repository: BasePolicyRepository | None = None,
        memory_store: BaseBrandMemoryStore | None = None,
    ):
        self.settings = settings
        self.repository = repository or make_repository(settings)
        self.memory_store = memory_store or get_brand_memory_store()

    def get_brand_memory(self, brand_id: Optional[str] = None) -> Optional[BrandMemory]:
        """Retrieve persistent brand memory for specified or default brand."""
        target_id = brand_id or self.settings.brand_id
        return self.memory_store.get_memory(target_id)

    def save_brand_memory(self, memory: BrandMemory) -> None:
        """Persist brand memory record."""
        self.memory_store.save_memory(memory)

    def update_brand_memory(self, updates: Dict[str, Any], brand_id: Optional[str] = None) -> BrandMemory:
        """Update explicit brand memory preferences."""
        target_id = brand_id or self.settings.brand_id
        return self.memory_store.update_preferences(target_id, updates)

    def resolve_brand_id(self, brand_id: Optional[str] = None) -> str:
        """Resolve the brand for a single review request.

        Resolution order: explicit per-request brand, then the configured
        workspace default (ENGANO_BRAND_ID). There is no hardcoded fallback
        brand: if neither is provided, a clear error is raised instead of
        silently reviewing under a sample brand.
        """
        resolved = (brand_id or self.settings.brand_id or "").strip().lower()
        if not resolved:
            raise ValueError(
                "No brand could be resolved for this review: pass an explicit "
                "brand_id or configure ENGANO_BRAND_ID."
            )
        return resolved

    async def review_text(
        self, draft_id: str, text: str, brand_id: Optional[str] = None
    ) -> ReviewResult:
        """Review text for an explicitly resolved brand.

        The brand and draft remain associated through the whole review and
        rewrite lifecycle; memory is fetched for the same resolved brand.
        """
        resolved_brand = self.resolve_brand_id(brand_id)
        request = ReviewInput(draft_id=draft_id, brand_id=resolved_brand, content_text=text)
        memory = self.get_brand_memory(resolved_brand)
        log.info(
            "Reviewing draft '%s' for brand '%s' (policy_source=%s)",
            draft_id,
            resolved_brand,
            self.settings.policy_source,
        )
        # run_brand_review is synchronous (and may call an LLM), so keep it off the event loop.
        return await asyncio.to_thread(run_brand_review, request, self.repository, None, None, memory)

    async def review_payload(self, payload: DraftPayload) -> ReviewResult:
        """Execute review directly on a normalized DraftPayload."""
        memory = self.get_brand_memory(payload.brand_id)
        return await asyncio.to_thread(run_brand_review, payload, self.repository, None, None, memory)

    def build_payload(self, channel: str, raw: Any, draft_id: Optional[str] = None) -> DraftPayload:
        """Normalize a channel's raw input with ai_engine's adapter for that channel.

        The brand always comes from our settings, never from the sender's message.
        """
        return get_adapter(channel).normalize(raw, self.settings.brand_id, draft_id)


def rewrite_check_note(result: ReviewResult) -> str | None:
    """ai_engine re-reviews its own rewrite; say whether it passed."""
    after = result.post_rewrite_decision
    if after is None:
        return None
    if after.status == ReviewDecision.GREEN:
        return "Re-checked: the rewrite passes."
    count = len(result.post_rewrite_findings)
    return f"Re-checked: the rewrite still has {count} issue{'s' if count != 1 else ''}."


# Finding categories whose enum value doesn't read well once underscores become spaces.
CATEGORY_LABELS = {"visual_wcag": "Accessibility"}


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category) or category.replace("_", " ").capitalize()
