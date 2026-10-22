import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
# The shared .env lives at the repo root (engano/.env).
ROOT_ENV = REPO_ROOT / ".env"

POLICY_SOURCES = ("supabase", "fixture")


@dataclass(frozen=True)
class Settings:
    bot_token: str
    # Set during development so commands sync to one server instantly.
    # Leave empty to register commands globally.
    guild_id: int | None
    # Web studio base URL. The "Open in studio" button is hidden until it is set.
    studio_url: str | None
    # Brand every Discord draft is checked against (one brand per bot for now).
    brand_id: str
    # Where brand policies come from: "supabase" (production) or "fixture"
    # (data/brand_library/*.json, local testing only). Never chosen implicitly.
    policy_source: str


def load_settings() -> Settings:
    # Loaded into os.environ so ai_engine's EngineConfig sees the same values.
    load_dotenv(ROOT_ENV)
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit(f"DISCORD_BOT_TOKEN is missing. Add it to {ROOT_ENV}")
    brand_id = os.getenv("ENGANO_BRAND_ID")
    if not brand_id:
        raise SystemExit(f"ENGANO_BRAND_ID is missing. Add it to {ROOT_ENV}")
    policy_source = os.getenv("ENGANO_POLICY_SOURCE", "supabase").strip().lower()
    if policy_source not in POLICY_SOURCES:
        raise SystemExit(f"ENGANO_POLICY_SOURCE must be one of {POLICY_SOURCES}, got {policy_source!r}")
    guild_id = os.getenv("DISCORD_GUILD_ID")
    return Settings(
        bot_token=token,
        guild_id=int(guild_id) if guild_id else None,
        studio_url=os.getenv("ENGANO_STUDIO_URL") or None,
        brand_id=brand_id,
        policy_source=policy_source,
    )
