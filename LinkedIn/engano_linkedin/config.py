import os
from dataclasses import dataclass
from pathlib import Path

from engano_backend.env import REPO_ROOT

DEFAULT_REDIRECT = "http://localhost:8000/api/oauth/linkedin/callback"


@dataclass(frozen=True)
class LinkedInSettings:
    # LinkedIn developer app > Auth tab.
    client_id: str | None
    client_secret: str | None
    # Must be listed under "Authorized redirect URLs" in the LinkedIn app.
    redirect_uri: str = DEFAULT_REDIRECT
    # Set to post as a company page (needs the Community Management API product,
    # which LinkedIn must approve). Empty: post as the connected member.
    organization_id: str | None = None
    # LinkedIn's versioned REST API (YYYYMM). Versions retire after about a year.
    api_version: str = "202608"
    # Local token cache until tokens move to Supabase. Git-ignored.
    token_path: Path = REPO_ROOT / "LinkedIn" / ".linkedin_token.json"

    @classmethod
    def from_env(cls) -> "LinkedInSettings":
        return cls(
            client_id=os.getenv("LINKEDIN_CLIENT_ID") or None,
            client_secret=os.getenv("LINKEDIN_CLIENT_SECRET") or None,
            redirect_uri=os.getenv("LINKEDIN_REDIRECT_URI") or DEFAULT_REDIRECT,
            organization_id=os.getenv("LINKEDIN_ORGANIZATION_ID") or None,
            api_version=os.getenv("LINKEDIN_API_VERSION") or "202608",
        )

    @property
    def scopes(self) -> list[str]:
        scopes = ["openid", "profile", "w_member_social"]
        if self.organization_id:
            scopes.append("w_organization_social")
        return scopes

    def missing(self) -> list[str]:
        return [name for name, value in (
            ("LINKEDIN_CLIENT_ID", self.client_id),
            ("LINKEDIN_CLIENT_SECRET", self.client_secret),
        ) if not value]
