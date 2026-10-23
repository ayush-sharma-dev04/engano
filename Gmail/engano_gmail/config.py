import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GmailSettings:
    # Dedicated review inbox, e.g. engano.review@gmail.com.
    address: str | None
    # Google Account > Security > 2-Step Verification > App passwords.
    app_password: str | None
    # Who may use the inbox: full addresses or "@domain". Empty means anyone.
    allowed_senders: tuple[str, ...] = ()
    poll_seconds: float = 15.0
    imap_host: str = "imap.gmail.com"
    smtp_host: str = "smtp.gmail.com"

    @classmethod
    def from_env(cls) -> "GmailSettings":
        allowed = os.getenv("GMAIL_ALLOWED_SENDERS", "")
        return cls(
            address=os.getenv("GMAIL_ADDRESS") or None,
            # Google shows app passwords in groups of four; spaces are optional.
            app_password=(os.getenv("GMAIL_APP_PASSWORD") or "").replace(" ", "") or None,
            allowed_senders=tuple(s.strip().lower() for s in allowed.split(",") if s.strip()),
            poll_seconds=float(os.getenv("GMAIL_POLL_SECONDS") or 15),
        )

    def missing(self) -> list[str]:
        return [name for name, value in (
            ("GMAIL_ADDRESS", self.address),
            ("GMAIL_APP_PASSWORD", self.app_password),
        ) if not value]

    def allows(self, sender: str) -> bool:
        if not self.allowed_senders:
            return True
        sender = sender.lower()
        return any(
            sender.endswith(rule) if rule.startswith("@") else sender == rule
            for rule in self.allowed_senders
        )
