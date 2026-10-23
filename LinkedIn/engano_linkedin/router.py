"""LinkedIn routes, mounted by the backend.

GET  /api/oauth/linkedin/start     sends you to LinkedIn to connect an account
GET  /api/oauth/linkedin/callback  LinkedIn sends you back here
GET  /api/linkedin/status          which account is connected
POST /api/linkedin/check           review a post (nothing is published)
POST /api/linkedin/publish         review, then publish only if GREEN and approved
"""

import logging
import secrets
from html import escape

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from engano_backend.review_service import ReviewService
from .client import LinkedInClient, LinkedInError
from .config import LinkedInSettings
from .token_store import TokenStore

log = logging.getLogger("engano.linkedin")

MAX_POST_LENGTH = 3000  # LinkedIn's limit for post text


class PostDraft(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_POST_LENGTH)


class PublishRequest(PostDraft):
    # Who approved this post. Required: ENGANO never publishes on its own.
    approved_by: str = Field(min_length=1)


def build_router(
    reviews: ReviewService,
    settings: LinkedInSettings,
    client: LinkedInClient,
    store: TokenStore,
) -> APIRouter:
    router = APIRouter(tags=["linkedin"])
    pending_states: set[str] = set()

    def require_configured() -> None:
        if missing := settings.missing():
            raise HTTPException(503, f"LinkedIn is not configured: set {', '.join(missing)} in .env")

    @router.get("/api/oauth/linkedin/start")
    async def start():
        require_configured()
        state = secrets.token_urlsafe(16)
        pending_states.add(state)
        return RedirectResponse(client.authorization_url(state))

    @router.get("/api/oauth/linkedin/callback", response_class=HTMLResponse)
    async def callback(
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
        error_description: str | None = Query(None),
    ):
        if error:
            raise HTTPException(400, f"LinkedIn declined: {error_description or error}")
        if not state or state not in pending_states:
            raise HTTPException(400, "Unknown or expired sign-in attempt. Start again at /api/oauth/linkedin/start")
        pending_states.discard(state)
        if not code:
            raise HTTPException(400, "LinkedIn didn't return an authorization code")
        try:
            token = await client.connect(code)
        except LinkedInError as exc:
            log.error("LinkedIn connect failed: %s", exc)
            raise HTTPException(502, str(exc)) from None
        store.save(token)
        log.info("LinkedIn connected as %s (%s)", token.member_name, token.member_urn)
        return (
            "<p style='font-family:sans-serif'>ENGANO is connected to LinkedIn as "
            f"<b>{escape(token.member_name or token.member_urn)}</b>. You can close this tab.</p>"
        )

    @router.get("/api/linkedin/status")
    async def status():
        token = store.load()
        return {
            "configured": not settings.missing(),
            "connected": bool(token and not token.expired),
            "connected_as": token.member_name if token else None,
            "posts_as": client.author_urn(token) if token else None,
            "token_expired": token.expired if token else None,
        }

    @router.post("/api/linkedin/check")
    async def check(draft: PostDraft):
        return await reviews.review_text(f"linkedin-check-{secrets.token_hex(4)}", draft.text)

    @router.post("/api/linkedin/publish")
    async def publish(req: PublishRequest):
        require_configured()
        token = store.load()
        if not token or token.expired:
            raise HTTPException(409, "No LinkedIn account connected. Open /api/oauth/linkedin/start first.")

        draft_id = f"linkedin-{secrets.token_hex(4)}"
        result = await reviews.review_text(draft_id, req.text)
        if result.completion_status != "completed" or result.decision.status.value != "GREEN":
            log.info("LinkedIn post %s blocked: %s", draft_id, result.decision.status.value)
            raise HTTPException(409, {
                "published": False,
                "reason": "Only posts the review marks GREEN can be published. Fix the findings and try again.",
                "review": result.model_dump(mode="json"),
            })

        try:
            post_urn = await client.create_post(token, req.text)
        except LinkedInError as exc:
            log.error("LinkedIn publish %s failed: %s", draft_id, exc)
            raise HTTPException(502, str(exc)) from None
        log.info("LinkedIn post %s published as %s, approved by %s", draft_id, post_urn, req.approved_by)
        return {
            "published": True,
            "post_urn": post_urn,
            "approved_by": req.approved_by,
            "review": result.model_dump(mode="json"),
        }

    return router
