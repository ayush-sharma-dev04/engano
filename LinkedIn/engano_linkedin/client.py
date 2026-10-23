import re
import time
from urllib.parse import urlencode

import httpx

from .config import LinkedInSettings
from .token_store import LinkedInToken

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
API = "https://api.linkedin.com"

# Post text uses LinkedIn's "little text" format, where these characters are
# markup. Unescaped, they can truncate the post or make the API reject it.
_LITTLE_TEXT_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")


def escape_commentary(text: str) -> str:
    return _LITTLE_TEXT_RESERVED.sub(r"\\\1", text)


class LinkedInError(RuntimeError):
    pass


class LinkedInClient:
    def __init__(self, settings: LinkedInSettings, http: httpx.AsyncClient | None = None):
        self.settings = settings
        self._http = http or httpx.AsyncClient(timeout=20.0)

    def authorization_url(self, state: str) -> str:
        return AUTH_URL + "?" + urlencode({
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": self.settings.redirect_uri,
            "state": state,
            "scope": " ".join(self.settings.scopes),
        })

    async def connect(self, code: str) -> LinkedInToken:
        """Exchange the OAuth code for a token and look up who connected."""
        resp = await self._http.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.redirect_uri,
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
        })
        if resp.is_error:
            raise LinkedInError(f"Token exchange failed (HTTP {resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        access_token = data["access_token"]

        me = await self._http.get(f"{API}/v2/userinfo", headers={"Authorization": f"Bearer {access_token}"})
        if me.is_error:
            raise LinkedInError(f"Couldn't read the LinkedIn profile (HTTP {me.status_code}): {me.text[:300]}")
        profile = me.json()
        return LinkedInToken(
            access_token=access_token,
            expires_at=time.time() + float(data.get("expires_in", 0)),
            member_urn=f"urn:li:person:{profile['sub']}",
            member_name=profile.get("name"),
        )

    def author_urn(self, token: LinkedInToken) -> str:
        if self.settings.organization_id:
            return f"urn:li:organization:{self.settings.organization_id}"
        return token.member_urn

    async def create_post(self, token: LinkedInToken, text: str) -> str:
        """Publish a text post. Returns the new post's URN."""
        resp = await self._http.post(
            f"{API}/rest/posts",
            headers={
                "Authorization": f"Bearer {token.access_token}",
                "LinkedIn-Version": self.settings.api_version,
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json={
                "author": self.author_urn(token),
                "commentary": escape_commentary(text),
                "visibility": "PUBLIC",
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": [],
                },
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            },
        )
        if resp.is_error:
            raise LinkedInError(f"LinkedIn rejected the post (HTTP {resp.status_code}): {resp.text[:300]}")
        return resp.headers.get("x-restli-id", "")

    async def aclose(self) -> None:
        await self._http.aclose()
