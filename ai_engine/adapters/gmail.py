"""Gmail channel adapter.

Normalizes email drafts and inbound messages originating from Gmail APIs or webhooks.
NOTE: This adapter provides boundary normalization and schema validation. Live production
connectivity requires configured Google Workspace credentials.
"""

import re
from typing import Any, List, Optional
import uuid
from ai_engine.adapters.base import BaseChannelAdapter
from ai_engine.schemas.payload import (
    ChannelType,
    DraftPayload,
    ImageItem,
)


def _strip_html(html_str: str) -> str:
    """Basic clean HTML strip for email body."""
    clean = re.sub(r"<[^>]+>", "", html_str)
    return " ".join(clean.split())


class GmailAdapter(BaseChannelAdapter):
    """Adapter for Gmail email drafts and messages."""

    def normalize(
        self,
        raw_input: Any,
        brand_id: str,
        draft_id: Optional[str] = None,
    ) -> DraftPayload:
        if raw_input is None:
            raise ValueError("Gmail payload cannot be None")

        if not isinstance(raw_input, dict):
            if isinstance(raw_input, str):
                raw_input = {"body": raw_input}
            else:
                raise ValueError(f"Expected dict or str for Gmail payload, got {type(raw_input).__name__}")

        msg_id = raw_input.get("id") or raw_input.get("message_id") or draft_id or str(uuid.uuid4())
        thread_id = raw_input.get("thread_id") or raw_input.get("threadId")
        subject = raw_input.get("subject", "").strip()
        body = raw_input.get("body") or raw_input.get("snippet") or ""

        # Handle HTML body if present
        if raw_input.get("body_html"):
            body = _strip_html(raw_input["body_html"])

        # Compose full review text: subject + body
        content_text = f"{subject}\n\n{body}".strip() if subject else body.strip()

        # Extract image attachments
        images: List[ImageItem] = []
        for att in raw_input.get("attachments", []):
            mime = att.get("mimeType", att.get("mime_type", ""))
            if mime.startswith("image/"):
                images.append(
                    ImageItem(
                        url=att.get("url") or att.get("filename"),
                        mime_type=mime,
                        alt_text=att.get("filename"),
                        metadata={"size": att.get("size")},
                    )
                )

        metadata = {
            "message_id": msg_id,
            "thread_id": thread_id,
            "subject": subject,
            "from": raw_input.get("from") or raw_input.get("sender"),
            "to": raw_input.get("to") or raw_input.get("recipient"),
        }

        return DraftPayload(
            draft_id=f"gmail-{msg_id}",
            brand_id=brand_id,
            channel=ChannelType.GMAIL,
            content_text=content_text,
            images=images,
            metadata=metadata,
        )
