"""Parse Meta webhook payloads into the messages we act on.

Shape: entry[].changes[].value.{metadata.phone_number_id, contacts[], messages[]}.
Delivery/read receipts arrive as value.statuses[] and are ignored.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    sender: str  # WhatsApp ID (phone number in international format, no +)
    phone_number_id: str  # our business number that received it; replies go out from it
    kind: str  # "text", "image", or another Meta type we don't review
    text: str = ""  # message body, or the image caption
    has_image: bool = False
    media_id: str = ""  # Meta media id of the image, used to download it


def parse_messages(payload: dict[str, Any]) -> list[IncomingMessage]:
    if payload.get("object") != "whatsapp_business_account":
        return []
    messages = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            if change.get("field") != "messages":
                continue
            value = change.get("value") or {}
            phone_number_id = (value.get("metadata") or {}).get("phone_number_id")
            if not phone_number_id:
                continue
            for msg in value.get("messages") or []:
                kind = msg.get("type", "unknown")
                media_id = ""
                if kind == "text":
                    text = (msg.get("text") or {}).get("body", "")
                elif kind == "image":
                    text = (msg.get("image") or {}).get("caption", "")
                    media_id = str((msg.get("image") or {}).get("id") or "")
                else:
                    text = ""
                messages.append(
                    IncomingMessage(
                        message_id=msg["id"],
                        sender=msg["from"],
                        phone_number_id=phone_number_id,
                        kind=kind,
                        text=text,
                        has_image=kind == "image",
                        media_id=media_id,
                    )
                )
    return messages
