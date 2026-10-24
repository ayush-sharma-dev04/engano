"""WhatsApp channel adapter.

Normalizes messages and image attachments originating from WhatsApp Business Webhooks
using payload models defined in WhatsApp/engano_whatsapp/payload.py.
"""

from typing import Any, List, Optional
import uuid
from ai_engine.adapters.base import BaseChannelAdapter
from ai_engine.schemas.payload import (
    ChannelType,
    DraftPayload,
    ImageItem,
    VisualMetadata,
)


class WhatsAppAdapter(BaseChannelAdapter):
    """Adapter for WhatsApp messaging payloads."""

    def normalize(
        self,
        raw_input: Any,
        brand_id: str,
        draft_id: Optional[str] = None,
    ) -> DraftPayload:
        if raw_input is None:
            raise ValueError("WhatsApp payload cannot be None")

        resolved_draft_id = draft_id
        text = ""
        images: List[ImageItem] = []
        metadata: dict[str, Any] = {}

        # Handle IncomingMessage dataclass from engano_backend.whatsapp
        if hasattr(raw_input, "message_id") and hasattr(raw_input, "sender"):
            msg_id = getattr(raw_input, "message_id")
            resolved_draft_id = resolved_draft_id or f"whatsapp-{msg_id}"
            text = getattr(raw_input, "text", "") or ""
            sender = getattr(raw_input, "sender", "")
            phone_number_id = getattr(raw_input, "phone_number_id", "")
            has_image = getattr(raw_input, "has_image", False)
            kind = getattr(raw_input, "kind", "text")

            metadata = {
                "message_id": msg_id,
                "sender": sender,
                "phone_number_id": phone_number_id,
                "kind": kind,
            }

            if has_image:
                images.append(
                    ImageItem(
                        mime_type="image/jpeg",
                        metadata={"whatsapp_media": True, "source": "whatsapp_webhook"},
                    )
                )

        elif isinstance(raw_input, dict):
            # Check if Meta payload or single message dict
            msg_id = raw_input.get("message_id") or raw_input.get("id") or str(uuid.uuid4())
            resolved_draft_id = resolved_draft_id or f"whatsapp-{msg_id}"
            img_data = raw_input.get("image") or {}
            text = (
                raw_input.get("text")
                or raw_input.get("caption")
                or raw_input.get("body")
                or img_data.get("caption")
                or ""
            )

            metadata = {
                "sender": raw_input.get("sender") or raw_input.get("from"),
                "phone_number_id": raw_input.get("phone_number_id"),
                "message_id": msg_id,
            }

            if raw_input.get("has_image") or raw_input.get("image") or raw_input.get("type") == "image":
                img_data = raw_input.get("image") or {}
                images.append(
                    ImageItem(
                        url=img_data.get("url"),
                        mime_type=img_data.get("mime_type", "image/jpeg"),
                        alt_text=img_data.get("caption"),
                        metadata={"media_id": img_data.get("id")},
                    )
                )
        elif isinstance(raw_input, str):
            text = raw_input
            resolved_draft_id = resolved_draft_id or f"whatsapp-{uuid.uuid4().hex[:8]}"
        else:
            raise ValueError(f"Unsupported WhatsApp payload type: {type(raw_input).__name__}")

        # If image exists and has alt text / visual clues, construct visual_metadata
        visual_metadata = None
        if images:
            visual_metadata = VisualMetadata(
                has_alt_text=bool(any(img.alt_text for img in images)),
            )

        return DraftPayload(
            draft_id=resolved_draft_id,
            brand_id=brand_id,
            channel=ChannelType.WHATSAPP,
            content_text=text,
            images=images,
            visual_metadata=visual_metadata,
            metadata=metadata,
        )
