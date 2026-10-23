import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WhatsAppSettings:
    # Meta app > WhatsApp > API Setup (temporary) or a system-user token (permanent).
    access_token: str | None
    # Meta app > App settings > Basic > App secret. Used to verify X-Hub-Signature-256.
    app_secret: str | None
    # Any string you choose; paste the same value into the Meta webhook settings.
    verify_token: str | None
    graph_version: str = "v25.0"

    @classmethod
    def from_env(cls) -> "WhatsAppSettings":
        return cls(
            access_token=os.getenv("WHATSAPP_ACCESS_TOKEN") or None,
            app_secret=os.getenv("WHATSAPP_APP_SECRET") or None,
            verify_token=os.getenv("WHATSAPP_VERIFY_TOKEN") or None,
            graph_version=os.getenv("WHATSAPP_GRAPH_VERSION") or "v25.0",
        )

    def missing(self) -> list[str]:
        problems = []
        if not self.verify_token:
            problems.append("WHATSAPP_VERIFY_TOKEN not set; Meta can't verify the webhook")
        if not self.app_secret:
            problems.append("WHATSAPP_APP_SECRET not set; incoming messages will be refused")
        if not self.access_token:
            problems.append("WHATSAPP_ACCESS_TOKEN not set; replies can't be sent")
        return problems
