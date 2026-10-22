import os
from dataclasses import dataclass

from engano_backend.env import ROOT_ENV, load_env


@dataclass(frozen=True)
class Settings:
    bot_token: str
    # Set during development so commands sync to one server instantly.
    # Leave empty to register commands globally.
    guild_id: int | None
    # Web studio base URL. The "Open in studio" button is hidden until it is set.
    studio_url: str | None


def load_settings() -> Settings:
    load_env()
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit(f"DISCORD_BOT_TOKEN is missing. Add it to {ROOT_ENV}")
    guild_id = os.getenv("DISCORD_GUILD_ID")
    return Settings(
        bot_token=token,
        guild_id=int(guild_id) if guild_id else None,
        studio_url=os.getenv("ENGANO_STUDIO_URL") or None,
    )
