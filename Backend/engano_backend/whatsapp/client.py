import logging

import httpx

log = logging.getLogger("engano.whatsapp")


class WhatsAppClient:
    """Minimal WhatsApp Cloud API client: send text replies and read receipts."""

    def __init__(self, access_token: str | None, graph_version: str, http: httpx.AsyncClient | None = None):
        self._token = access_token
        self._base = f"https://graph.facebook.com/{graph_version}"
        self._http = http or httpx.AsyncClient(timeout=15.0)

    async def _post(self, phone_number_id: str, body: dict) -> None:
        if not self._token:
            raise RuntimeError("WHATSAPP_ACCESS_TOKEN is not set")
        resp = await self._http.post(
            f"{self._base}/{phone_number_id}/messages",
            json={"messaging_product": "whatsapp", **body},
            headers={"Authorization": f"Bearer {self._token}"},
        )
        if resp.is_error:
            # Meta's error body explains the cause (expired token, recipient not allowed, ...).
            raise RuntimeError(f"WhatsApp API HTTP {resp.status_code}: {resp.text[:500]}")

    async def send_text(self, phone_number_id: str, to: str, text: str, reply_to: str | None = None) -> None:
        body: dict = {
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": False},
        }
        if reply_to:
            body["context"] = {"message_id": reply_to}
        await self._post(phone_number_id, body)

    async def mark_read(self, phone_number_id: str, message_id: str) -> None:
        await self._post(phone_number_id, {"status": "read", "message_id": message_id})

    async def aclose(self) -> None:
        await self._http.aclose()
