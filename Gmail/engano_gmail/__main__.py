"""Run the Gmail review inbox: `make gmail` (python -m engano_backend.gmail)."""

import asyncio
import imaplib
import logging
import sys

from engano_backend.env import load_env
from engano_backend.review_service import ReviewService, ReviewSettings
from .config import GmailSettings
from .mailbox import GmailMailbox
from .worker import GmailWorker

log = logging.getLogger("engano.gmail")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_env()
    settings = GmailSettings.from_env()
    if missing := settings.missing():
        log.info("Gmail not configured (%s missing in .env). Skipping.", ", ".join(missing))
        return
    if not settings.allowed_senders:
        log.warning("GMAIL_ALLOWED_SENDERS is empty: anyone who emails %s gets a review.", settings.address)

    mailbox = GmailMailbox(settings)
    try:
        mailbox.check_login()
    except imaplib.IMAP4.error as exc:
        sys.exit(
            f"Gmail login failed for {settings.address}: {exc}. "
            "Use an app password (Google Account > Security > App passwords), not your normal password."
        )
    worker = GmailWorker(ReviewService(ReviewSettings.from_env()), settings, mailbox)
    try:
        asyncio.run(worker.run_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
