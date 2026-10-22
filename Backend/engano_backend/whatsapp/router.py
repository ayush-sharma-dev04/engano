"""Webhook routes, mounted at /api/webhooks/whatsapp.

GET  answers Meta's one-time verification handshake.
POST receives messages: verify the signature, acknowledge at once (Meta retries
slow webhooks), then review and reply in a background task.
"""

import hmac
import json
import logging
from collections import OrderedDict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from ..review_service import ReviewService
from .client import WhatsAppClient
from .config import WhatsAppSettings
from .payload import IncomingMessage, parse_messages
from .render import (
    ERROR_TEXT,
    HELP_TEXT,
    IMAGE_ONLY_TEXT,
    UNSUPPORTED_TEXT,
    is_help_request,
    render_result,
)
from .signature import verify_signature

log = logging.getLogger("engano.whatsapp")


class _RecentIds:
    """Meta can deliver the same message more than once; remember recent IDs."""

    def __init__(self, size: int = 1000):
        self._ids: OrderedDict[str, None] = OrderedDict()
        self._size = size

    def seen(self, message_id: str) -> bool:
        if message_id in self._ids:
            return True
        self._ids[message_id] = None
        if len(self._ids) > self._size:
            self._ids.popitem(last=False)
        return False


def build_router(
    review_service: ReviewService,
    settings: WhatsAppSettings,
    client: WhatsAppClient,
) -> APIRouter:
    router = APIRouter(tags=["whatsapp"])
    recent = _RecentIds()

    async def reply(msg: IncomingMessage, text: str) -> None:
        await client.send_text(msg.phone_number_id, msg.sender, text, reply_to=msg.message_id)

    async def handle(msg: IncomingMessage) -> None:
        try:
            try:
                await client.mark_read(msg.phone_number_id, msg.message_id)
            except Exception as exc:  # read receipts are cosmetic
                log.warning("Couldn't mark %s as read: %s", msg.message_id, exc)

            if msg.kind not in ("text", "image"):
                await reply(msg, UNSUPPORTED_TEXT)
                return
            if not msg.text.strip():
                await reply(msg, IMAGE_ONLY_TEXT)
                return
            if msg.kind == "text" and is_help_request(msg.text):
                await reply(msg, HELP_TEXT)
                return

            draft_id = f"whatsapp-{msg.message_id}"
            try:
                result = await review_service.review_text(draft_id, msg.text)
            except Exception:
                log.exception("Review %s failed", draft_id)
                await reply(msg, ERROR_TEXT)
                return
            log.info(
                "Review %s: %s (%s, %d findings)",
                draft_id, result.decision.status.value, result.completion_status, len(result.findings),
            )
            await reply(msg, render_result(result, msg.text, had_image=msg.has_image))
        except Exception:
            log.exception("Couldn't handle WhatsApp message %s", msg.message_id)

    @router.get("", response_class=PlainTextResponse)
    async def verify_webhook(
        mode: str | None = Query(None, alias="hub.mode"),
        token: str | None = Query(None, alias="hub.verify_token"),
        challenge: str | None = Query(None, alias="hub.challenge"),
    ):
        if (
            mode == "subscribe"
            and settings.verify_token
            and token
            and hmac.compare_digest(token, settings.verify_token)
        ):
            log.info("WhatsApp webhook verified by Meta")
            return challenge or ""
        raise HTTPException(status_code=403, detail="Verification failed")

    @router.post("")
    async def receive(request: Request, background: BackgroundTasks):
        if not settings.app_secret:
            log.error("Refusing WhatsApp webhook: WHATSAPP_APP_SECRET is not set")
            raise HTTPException(status_code=503, detail="Webhook not configured")
        raw = await request.body()
        if not verify_signature(raw, request.headers.get("X-Hub-Signature-256"), settings.app_secret):
            raise HTTPException(status_code=401, detail="Invalid signature")
        try:
            payload = json.loads(raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid JSON") from None

        for msg in parse_messages(payload):
            if recent.seen(msg.message_id):
                continue
            background.add_task(handle, msg)
        return {"status": "received"}

    return router
