import asyncio
import logging
from email.message import EmailMessage
from email.utils import make_msgid

from engano_backend.review_service import ReviewService
from .config import GmailSettings
from .mailbox import GmailMailbox
from .parse import IncomingEmail, parse_email
from .render import ERROR_TEXT, FOOTER, HELP_TEXT, render_reply

log = logging.getLogger("engano.gmail")


class GmailWorker:
    def __init__(self, reviews: ReviewService, settings: GmailSettings, mailbox: GmailMailbox):
        self.reviews = reviews
        self.settings = settings
        self.mailbox = mailbox

    async def poll_once(self) -> int:
        messages = await asyncio.to_thread(self.mailbox.fetch_unread)
        for uid, raw in messages:
            try:
                await self.handle(raw)
            except Exception:
                log.exception("Couldn't handle email uid %s", uid.decode())
            # Mark read even after a failure, so one bad email can't loop forever.
            await asyncio.to_thread(self.mailbox.mark_read, uid)
        return len(messages)

    async def handle(self, raw: bytes) -> None:
        mail = parse_email(raw)
        if mail.sender == (self.settings.address or "").lower():
            return
        if mail.is_automated:
            log.info("Ignoring automated email from %s", mail.sender)
            return
        if not self.settings.allows(mail.sender):
            log.info("Ignoring email from %s: not in GMAIL_ALLOWED_SENDERS", mail.sender)
            return

        if not mail.draft:
            await self._reply(mail, HELP_TEXT + f"\n\n--\n{FOOTER}")
            return

        draft_id = f"gmail-{abs(hash(mail.message_id or raw)) % 10**10}"
        try:
            result = await self.reviews.review_text(draft_id, mail.draft)
        except Exception:
            log.exception("Review %s failed", draft_id)
            await self._reply(mail, ERROR_TEXT)
            return
        log.info(
            "Review %s from %s: %s (%s, %d findings)",
            draft_id, mail.sender, result.decision.status.value, result.completion_status, len(result.findings),
        )
        text, html = render_reply(result, mail.draft, mail.image_count)
        await self._reply(mail, text, html)

    async def _reply(self, mail: IncomingEmail, text: str, html: str | None = None) -> None:
        await asyncio.to_thread(self.mailbox.send, self.build_reply(mail, text, html))

    def build_reply(self, mail: IncomingEmail, text: str, html: str | None = None) -> EmailMessage:
        reply = EmailMessage()
        reply["From"] = f"ENGANO Brand Review <{self.settings.address}>"
        reply["To"] = mail.reply_to
        subject = mail.subject or "Your draft"
        reply["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        reply["Message-ID"] = make_msgid(domain=(self.settings.address or "engano").split("@")[-1])
        # Threading: Gmail and other clients group the reply with the original.
        if mail.message_id:
            reply["In-Reply-To"] = mail.message_id
            reply["References"] = f"{mail.references} {mail.message_id}".strip() if mail.references else mail.message_id
        reply["Auto-Submitted"] = "auto-replied"
        reply.set_content(text)
        if html:
            reply.add_alternative(html, subtype="html")
        return reply

    async def run_forever(self) -> None:
        log.info(
            "Watching %s every %.0f s (%s)",
            self.settings.address, self.settings.poll_seconds,
            "allowed: " + ", ".join(self.settings.allowed_senders) if self.settings.allowed_senders else "open to any sender",
        )
        while True:
            try:
                handled = await self.poll_once()
                if handled:
                    log.info("Handled %d email(s)", handled)
            except Exception as exc:  # network hiccups: keep polling
                log.warning("Polling failed: %s", exc)
            await asyncio.sleep(self.settings.poll_seconds)
