"""Turn a raw email into the draft text to review."""

import html
import re
from dataclasses import dataclass
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr

FORWARD_MARKERS = (
    "---------- Forwarded message ---------",  # Gmail
    "-------- Original Message --------",  # Thunderbird
    "-----Original Message-----",  # Outlook
    "Begin forwarded message:",  # Apple Mail
)
HEADER_LINE = re.compile(r"^\s*(From|Date|Sent|Subject|To|Cc)\s*:", re.IGNORECASE)
QUOTE_INTRO = re.compile(r"^On .+wrote:\s*$")
AUTOMATED_SENDER = re.compile(r"(no-?reply|mailer-daemon|postmaster|bounce)", re.IGNORECASE)


@dataclass(frozen=True)
class IncomingEmail:
    message_id: str | None
    references: str | None
    sender: str  # address only
    reply_to: str  # where the answer goes (Reply-To, else From)
    subject: str
    draft: str  # text to review
    image_count: int
    is_automated: bool


def parse_email(raw: bytes) -> IncomingEmail:
    msg: EmailMessage = message_from_bytes(raw, policy=policy.default)  # type: ignore[assignment]
    sender = parseaddr(str(msg.get("From", "")))[1].lower()
    reply_to = getaddresses([str(msg.get("Reply-To", ""))])
    subject = str(msg.get("Subject", "")).strip()
    return IncomingEmail(
        message_id=msg.get("Message-ID"),
        references=msg.get("References"),
        sender=sender,
        reply_to=(reply_to[0][1] if reply_to and reply_to[0][1] else sender),
        subject=subject,
        draft=extract_draft(_body_text(msg)),
        image_count=sum(1 for part in msg.walk() if part.get_content_maintype() == "image"),
        is_automated=_is_automated(msg, sender),
    )


def extract_draft(body: str) -> str:
    """The forwarded message (subject + body) if there is one, else the body minus quotes and signature."""
    body = body.replace("\r\n", "\n")
    for marker in FORWARD_MARKERS:
        if marker in body:
            return _forwarded_part(body.split(marker, 1)[1])
    return _strip_quotes_and_signature(body)


def _forwarded_part(text: str) -> str:
    lines = text.lstrip("\n").split("\n")
    subject = ""
    i = 0
    # Skip the forwarded header block (From:, Date:, Subject:, To:), keeping the subject.
    while i < len(lines) and (HEADER_LINE.match(lines[i]) or not lines[i].strip()):
        if lines[i].strip().lower().startswith("subject:"):
            subject = lines[i].split(":", 1)[1].strip()
        if not lines[i].strip() and i > 0:
            i += 1
            break
        i += 1
    rest = _strip_quotes_and_signature("\n".join(lines[i:]))
    return f"{subject}\n\n{rest}".strip() if subject else rest


def _strip_quotes_and_signature(text: str) -> str:
    kept = []
    for line in text.split("\n"):
        if line.rstrip() == "--" or QUOTE_INTRO.match(line.strip()):
            break
        if line.lstrip().startswith(">"):
            continue
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def _body_text(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    return _html_to_text(content) if part.get_content_subtype() == "html" else content


def _html_to_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", "", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h[1-6])>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", "", markup))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def _is_automated(msg: EmailMessage, sender: str) -> bool:
    """Never answer bounces, mailing lists or other robots (avoids reply loops)."""
    auto_submitted = str(msg.get("Auto-Submitted", "no")).lower()
    precedence = str(msg.get("Precedence", "")).lower()
    return (
        auto_submitted != "no"
        or precedence in ("bulk", "junk", "list")
        or msg.get("List-Id") is not None
        or bool(AUTOMATED_SENDER.search(sender.split("@")[0]))
    )
