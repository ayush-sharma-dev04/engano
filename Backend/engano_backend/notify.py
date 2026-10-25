"""Tell a reviewer, on the platforms they chose, that a draft is waiting.

A reviewer can save a WhatsApp number and/or a Discord user ID in Settings. When a creator
sends a draft that needs a person, every reviewer of that workspace who saved a contact gets
the draft, ENGANO's findings and a link to decide in the studio. Delivery is best effort: a
failure is logged and reported, and never stops the draft from reaching the review queue.
"""

import logging
import os
import re

import httpx

from engano_whatsapp.client import WhatsAppClient

log = logging.getLogger("engano.notify")

DISCORD_API = "https://discord.com/api/v10"
MAX_DRAFT = 1200
MAX_FINDINGS = 5


def normalize_whatsapp(raw: str | None) -> str | None:
    """Country code + number, digits only (WhatsApp's wa_id form). None if it cannot be one."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    if len(digits) == 10:  # a national number: add the default country code
        digits = (re.sub(r"\D", "", os.getenv("ENGANO_DEFAULT_COUNTRY_CODE", "")) or "91") + digits
    return digits if 8 <= len(digits) <= 15 else None


def normalize_discord(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    return digits if 15 <= len(digits) <= 20 else None


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def review_request_text(workspace: str, creator: str, submission: dict) -> str:
    verdict = {"GREEN": "looks clean", "YELLOW": "needs a look", "RED": "has serious problems"}.get(submission.get("aiStatus") or "", "was not rated")
    lines = [
        "ENGANO: a draft is waiting for your review",
        f"Workspace: {workspace}  |  From: {creator}",
        f"Title: {submission['title']}",
        f"ENGANO says it {verdict}.",
        "",
        "Draft:",
        _clip(submission["content"], MAX_DRAFT),
    ]
    findings = submission.get("findings") or []
    if findings:
        lines += ["", "Findings:"]
        for i, f in enumerate(findings[:MAX_FINDINGS], 1):
            lines.append(f"{i}. {_clip(str(f.get('issue', '')), 140)} ({f.get('severity', '')})")
            if f.get("explanation"):
                lines.append(f"   {_clip(str(f['explanation']), 240)}")
        if len(findings) > MAX_FINDINGS:
            lines.append(f"...and {len(findings) - MAX_FINDINGS} more")
    studio = os.getenv("ENGANO_STUDIO_URL")
    lines.append(f"\nApprove or reject it in the studio: {studio}" if studio else "\nApprove or reject it in the ENGANO studio.")
    return "\n".join(lines)


class ReviewerNotifier:
    def __init__(self, whatsapp: WhatsAppClient | None, discord_token: str | None, graph_version: str = "v25.0", http: httpx.AsyncClient | None = None):
        self._whatsapp = whatsapp
        self._discord_token = (discord_token or "").strip()
        self._graph = f"https://graph.facebook.com/{graph_version}"
        self._http = http or httpx.AsyncClient(timeout=15.0)
        self._phone_number_id: str | None = None

    @classmethod
    def from_env(cls, whatsapp: WhatsAppClient | None, graph_version: str = "v25.0") -> "ReviewerNotifier":
        return cls(whatsapp, os.getenv("DISCORD_BOT_TOKEN"), graph_version)

    async def _sender_id(self) -> str:
        """The WhatsApp business number messages are sent from: from .env, else asked of Meta once."""
        if self._phone_number_id:
            return self._phone_number_id
        configured = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
        if configured:
            self._phone_number_id = configured
            return configured
        waba, token = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "").strip(), os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
        if not (waba and token):
            raise RuntimeError("Set WHATSAPP_PHONE_NUMBER_ID (or WHATSAPP_BUSINESS_ACCOUNT_ID) in .env to send WhatsApp messages.")
        r = await self._http.get(f"{self._graph}/{waba}/phone_numbers", headers={"Authorization": f"Bearer {token}"})
        if r.is_error:
            raise RuntimeError(f"Could not find the WhatsApp sender number (HTTP {r.status_code}).")
        numbers = r.json().get("data") or []
        if not numbers:
            raise RuntimeError("The WhatsApp business account has no phone number.")
        self._phone_number_id = str(numbers[0]["id"])
        return self._phone_number_id

    async def _send_whatsapp(self, number: str, text: str) -> None:
        if not self._whatsapp:
            raise RuntimeError("WhatsApp is not set up on this server.")
        await self._whatsapp.send_text(await self._sender_id(), number, text)

    async def _send_discord(self, user_id: str, text: str) -> None:
        if not self._discord_token:
            raise RuntimeError("DISCORD_BOT_TOKEN is not set on this server.")
        headers = {"Authorization": f"Bot {self._discord_token}"}
        dm = await self._http.post(f"{DISCORD_API}/users/@me/channels", json={"recipient_id": user_id}, headers=headers)
        if dm.is_error:
            raise RuntimeError(f"Discord would not open a message to that user (HTTP {dm.status_code}). They must share a server with the bot.")
        sent = await self._http.post(
            f"{DISCORD_API}/channels/{dm.json()['id']}/messages", json={"content": text[:2000]}, headers=headers
        )
        if sent.is_error:
            raise RuntimeError(f"Discord refused the message (HTTP {sent.status_code}). Their privacy settings may block DMs from the bot.")

    async def send(self, contact: dict, text: str) -> dict[str, str]:
        """Send to each saved platform. Returns {platform: "sent" | the reason it failed}."""
        out: dict[str, str] = {}
        for platform, value, sender in (
            ("WhatsApp", contact.get("whatsapp"), self._send_whatsapp),
            ("Discord", contact.get("discord_id"), self._send_discord),
        ):
            if not value:
                continue
            try:
                await sender(value, text)
                out[platform] = "sent"
            except Exception as exc:  # delivery is best effort
                log.warning("Reviewer notification via %s failed: %s", platform, exc)
                out[platform] = str(exc)[:300]
        return out

    async def aclose(self) -> None:
        await self._http.aclose()
