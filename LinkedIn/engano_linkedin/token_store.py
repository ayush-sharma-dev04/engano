import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class LinkedInToken:
    access_token: str
    expires_at: float  # unix time
    member_urn: str  # urn:li:person:<id> of whoever connected
    member_name: str | None = None

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at - 60


class TokenStore:
    """One connected LinkedIn account, cached in a local file (mode 600)."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> LinkedInToken | None:
        try:
            return LinkedInToken(**json.loads(self.path.read_text()))
        except (FileNotFoundError, ValueError, TypeError):
            return None

    def save(self, token: LinkedInToken) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(asdict(token), f)
