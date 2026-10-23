"""Gmail adapter tests: real ai_engine + Nimbus fixture, fake mailbox."""

import asyncio
from email.message import EmailMessage

import pytest

from engano_backend.review_service import ReviewService, ReviewSettings
from engano_gmail.config import GmailSettings
from engano_gmail.parse import extract_draft, parse_email
from engano_gmail.worker import GmailWorker

INBOX = "engano.review@gmail.com"
BAD_DRAFT = "NimbusDB is the fastest database in the world, with 100% uptime. Try it free forever!"


class FakeMailbox:
    def __init__(self, messages=()):
        self.unread = [(str(i).encode(), raw) for i, raw in enumerate(messages, 1)]
        self.read: list[bytes] = []
        self.sent: list[EmailMessage] = []

    def fetch_unread(self):
        return [m for m in self.unread if m[0] not in self.read]

    def mark_read(self, uid):
        self.read.append(uid)

    def send(self, message):
        self.sent.append(message)


def email(body: str, sender="writer@example.com", subject="Launch post", html: str | None = None, **headers) -> bytes:
    msg = EmailMessage()
    msg["From"] = f"Writer <{sender}>"
    msg["To"] = INBOX
    msg["Subject"] = subject
    msg["Message-ID"] = "<original-1@example.com>"
    for name, value in headers.items():
        msg[name.replace("_", "-")] = value
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    return bytes(msg)


def run(messages, **settings):
    mailbox = FakeMailbox(messages)
    reviews = ReviewService(ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"))
    worker = GmailWorker(reviews, GmailSettings(address=INBOX, app_password="x", **settings), mailbox)
    asyncio.run(worker.poll_once())
    return mailbox


def text_of(message: EmailMessage) -> str:
    return message.get_body(preferencelist=("plain",)).get_content()


def test_reviews_draft_and_replies_in_thread():
    mailbox = run([email(BAD_DRAFT)])
    [reply] = mailbox.sent
    assert reply["To"] == "writer@example.com"
    assert reply["Subject"] == "Re: Launch post"
    assert reply["In-Reply-To"] == "<original-1@example.com>"
    assert reply["Auto-Submitted"] == "auto-replied"
    body = text_of(reply)
    assert "Needs reviewer approval" in body
    assert '"NimbusDB" → "Nimbus DB"' in body
    assert "Suggested rewrite:" in body
    html = reply.get_body(preferencelist=("html",)).get_content()
    assert "99.95% uptime SLA" in html
    assert mailbox.read == [b"1"]


def test_forwarded_draft_reviews_only_the_forwarded_part():
    body = (
        "Can you check this before Friday?\n\n"
        "---------- Forwarded message ---------\n"
        "From: Agency <agency@example.com>\n"
        "Date: Thu, 22 Oct 2026\n"
        "Subject: Nimbus launch newsletter\n"
        "To: me@example.com\n\n"
        f"{BAD_DRAFT}\n\n-- \nAgency team\n"
    )
    assert extract_draft(body) == f"Nimbus launch newsletter\n\n{BAD_DRAFT}"
    mailbox = run([email(body, subject="Fwd: Nimbus launch newsletter")])
    assert "Needs reviewer approval" in text_of(mailbox.sent[0])


def test_quotes_and_signature_are_not_reviewed():
    body = f"Nimbus DB keeps your data safe.\n\n-- \nNimbusDB fan\n\nOn Mon, someone wrote:\n> {BAD_DRAFT}"
    assert extract_draft(body) == "Nimbus DB keeps your data safe."


def test_html_only_email():
    msg = EmailMessage()
    msg["From"] = "writer@example.com"
    msg["Subject"] = "HTML draft"
    msg.set_content(f"<p>{BAD_DRAFT.replace('free forever', '<b>free forever</b>')}</p>", subtype="html")
    assert parse_email(bytes(msg)).draft == BAD_DRAFT


def test_clean_draft_is_green_without_rewrite():
    mailbox = run([email("Nimbus DB keeps your data safe with a 99.95% uptime SLA.")])
    body = text_of(mailbox.sent[0])
    assert "Ready to publish" in body and "Suggested rewrite" not in body


def test_empty_email_gets_help():
    mailbox = run([email("")])
    assert "Forward a draft" in text_of(mailbox.sent[0])


@pytest.mark.parametrize("headers", [
    {"Auto_Submitted": "auto-replied"},
    {"Precedence": "bulk"},
    {"List_Id": "<news.example.com>"},
])
def test_ignores_automated_mail(headers):
    mailbox = run([email(BAD_DRAFT, **headers)])
    assert mailbox.sent == [] and mailbox.read == [b"1"]


def test_ignores_noreply_and_own_address():
    mailbox = run([email(BAD_DRAFT, sender="no-reply@example.com"), email(BAD_DRAFT, sender=INBOX)])
    assert mailbox.sent == [] and len(mailbox.read) == 2


def test_allowed_senders():
    mailbox = run(
        [email(BAD_DRAFT, sender="writer@nimbus.example"), email(BAD_DRAFT, sender="stranger@other.example")],
        allowed_senders=("@nimbus.example",),
    )
    assert [m["To"] for m in mailbox.sent] == ["writer@nimbus.example"]


def test_reply_to_header_is_respected():
    mailbox = run([email(BAD_DRAFT, Reply_To="team@example.com")])
    assert mailbox.sent[0]["To"] == "team@example.com"


def test_images_are_flagged_as_not_checked():
    msg = EmailMessage()
    msg["From"] = "writer@example.com"
    msg["Subject"] = "Flyer"
    msg.set_content(BAD_DRAFT)
    msg.add_attachment(b"\x89PNG fake", maintype="image", subtype="png", filename="flyer.png")
    mailbox = run([bytes(msg)])
    assert "Images were not checked" in text_of(mailbox.sent[0])
