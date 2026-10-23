"""LinkedIn channel adapter.

Normalizes draft posts and commentary originating from LinkedIn marketing tools or webhooks.
NOTE: This adapter provides boundary normalization and schema validation. Live production
connectivity requires configured LinkedIn Developer App credentials.
"""

from typing import Any, List, Optional
import uuid
from ai_engine.adapters.base import BaseChannelAdapter
from ai_engine.schemas.payload import (
    ChannelType,
    DraftPayload,
    ImageItem,
)


class LinkedInAdapter(BaseChannelAdapter):
    """Adapter for LinkedIn post content and media."""

    def normalize(
        self,
        raw_input: Any,
        brand_id: str,
        draft_id: Optional[str] = None,
    ) -> DraftPayload:
        if raw_input is None:
            raise ValueError("LinkedIn payload cannot be None")

        if not isinstance(raw_input, dict):
            if isinstance(raw_input, str):
                raw_input = {"text": raw_input}
            else:
                raise ValueError(f"Expected dict or str for LinkedIn payload, got {type(raw_input).__name__}")

        post_urn = raw_input.get("post_urn") or raw_input.get("id") or str(uuid.uuid4())
        author_urn = raw_input.get("author_urn") or raw_input.get("author")
        text = (
            raw_input.get("commentary")
            or raw_input.get("text")
            or raw_input.get("content")
            or ""
        )

        # Extract media / images
        images: List[ImageItem] = []
        for media_entry in raw_input.get("media", []):
            if isinstance(media_entry, dict):
                images.append(
                    ImageItem(
                        url=media_entry.get("url") or media_entry.get("media_urn"),
                        alt_text=media_entry.get("alt_text") or media_entry.get("title"),
                        mime_type=media_entry.get("mime_type", "image/png"),
                        metadata={"title": media_entry.get("title")},
                    )
                )
            elif isinstance(media_entry, str):
                images.append(ImageItem(url=media_entry))

        metadata = {
            "post_urn": post_urn,
            "author_urn": author_urn,
            "visibility": raw_input.get("visibility", "PUBLIC"),
        }

        return DraftPayload(
            draft_id=draft_id or f"linkedin-{post_urn}",
            brand_id=brand_id,
            channel=ChannelType.LINKEDIN,
            content_text=text,
            images=images,
            metadata=metadata,
        )
