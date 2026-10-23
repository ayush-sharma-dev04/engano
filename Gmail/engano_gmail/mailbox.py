"""Blocking IMAP/SMTP access to the Gmail review inbox (called via asyncio.to_thread)."""

import imaplib
import smtplib
import ssl
from email.message import EmailMessage

from .config import GmailSettings

FETCH_LIMIT = 20


class GmailMailbox:
    def __init__(self, settings: GmailSettings):
        self.settings = settings

    def _imap(self) -> imaplib.IMAP4_SSL:
        imap = imaplib.IMAP4_SSL(self.settings.imap_host, ssl_context=ssl.create_default_context())
        imap.login(self.settings.address, self.settings.app_password)
        imap.select("INBOX")
        return imap

    def fetch_unread(self) -> list[tuple[bytes, bytes]]:
        """(uid, raw message) for unread inbox mail, without marking it read."""
        imap = self._imap()
        try:
            _, data = imap.uid("search", None, "UNSEEN")
            uids = data[0].split()[:FETCH_LIMIT]
            messages = []
            for uid in uids:
                _, parts = imap.uid("fetch", uid, "(BODY.PEEK[])")
                raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
                if raw:
                    messages.append((uid, raw))
            return messages
        finally:
            imap.logout()

    def mark_read(self, uid: bytes) -> None:
        imap = self._imap()
        try:
            imap.uid("store", uid, "+FLAGS", "(\\Seen)")
        finally:
            imap.logout()

    def send(self, message: EmailMessage) -> None:
        with smtplib.SMTP_SSL(self.settings.smtp_host, 465, context=ssl.create_default_context()) as smtp:
            smtp.login(self.settings.address, self.settings.app_password)
            smtp.send_message(message)

    def check_login(self) -> None:
        self._imap().logout()
