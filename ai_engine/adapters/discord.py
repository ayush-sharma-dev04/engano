"""Discord channel adapter.

Normalizes messages and interactions originating from Discord bots or integrations.
Preserves author and channel context without permitting overrides to trusted brand settings.
"""

from typing import Any, List, Optional
import uuid
from ai_engine.adapters.base import BaseChannelAdapter
from ai_engine.schemas.payload import (
    ChannelType,
    DraftPayload,
    ImageItem,
)


class DiscordAdapter(BaseChannelAdapter):
    """Adapter for Discord channel payloads."""

    def normalize(
        self,
        raw_input: Any,
        brand_id: str,
        draft_id: Optional[str] = None,
    ) -> DraftPayload:
        if raw_input is None:
            raise ValueError("Discord payload cannot be None")

        resolved_draft_id = draft_id
        text = ""
        image_urls: List[str] = []
        metadata: dict[str, Any] = {}

        # Handle Draft dataclass from engano_discord
        if hasattr(raw_input, "text") and hasattr(raw_input, "channel"):
            text = getattr(raw_input, "text", "")
            image_urls = getattr(raw_input, "image_urls", []) or []
            author_id = getattr(raw_input, "author_id", None)
            channel_name = getattr(raw_input, "channel", None)
            source_url = getattr(raw_input, "source_url", None)
            if not resolved_draft_id:
                resolved_draft_id = f"discord-{uuid.uuid4().hex[:8]}"
            metadata = {
                "author_id": author_id,
                "channel_name": channel_name,
                "source_url": source_url,
            }
        elif isinstance(raw_input, dict):
            # Dict payload
            resolved_draft_id = resolved_draft_id or raw_input.get("draft_id") or raw_input.get("message_id")
            if not resolved_draft_id:
                resolved_draft_id = f"discord-{uuid.uuid4().hex[:8]}"
            text = raw_input.get("text") or raw_input.get("content") or ""
            image_urls = raw_input.get("image_urls") or []
            # Extract attachments if discord payload format
            for att in raw_input.get("attachments", []):
                if isinstance(att, dict) and att.get("url"):
                    image_urls.append(att["url"])
                elif isinstance(att, str):
                    image_urls.append(att)
            metadata = {
                "author_id": raw_input.get("author_id"),
                "channel_id": raw_input.get("channel_id"),
                "guild_id": raw_input.get("guild_id"),
            }
        elif isinstance(raw_input, str):
            text = raw_input
            if not resolved_draft_id:
                resolved_draft_id = f"discord-{uuid.uuid4().hex[:8]}"
        else:
            raise ValueError(f"Unsupported Discord payload type: {type(raw_input).__name__}")

        images = [ImageItem(url=url) for url in image_urls]

        return DraftPayload(
            draft_id=resolved_draft_id,
            brand_id=brand_id,
            channel=ChannelType.DISCORD,
            content_text=text,
            images=images,
            metadata=metadata,
        )
