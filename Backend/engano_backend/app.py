import asyncio
import logging
import os
import secrets
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
from ai_engine.config import EngineConfig, get_engine_config
from ai_engine.schemas.brand_memory import BrandMemory
from ai_engine.schemas.review import ReviewResult

from engano_linkedin.client import LinkedInClient
from engano_linkedin.config import LinkedInSettings
from engano_linkedin.router import build_router as build_linkedin_router
from engano_linkedin.token_store import TokenStore
from engano_whatsapp.client import WhatsAppClient
from engano_whatsapp.config import WhatsAppSettings
from engano_whatsapp.router import build_router as build_whatsapp_router

from .escalation import EscalationSettings
from .review_service import ReviewService, ReviewSettings
from .auth_mirror import AuthMirror
from .notify import ReviewerNotifier
from .team_api import build_router as build_team_router
from .team_store import TeamStore
from .website import SiteError

log = logging.getLogger("engano.backend")

MAX_REVIEW_CHARS = 10_000


MAX_IMAGES = 4
MAX_IMAGE_B64_CHARS = 5_600_000  # about 4 MB of image


class ReviewImage(BaseModel):
    """One attached image: base64 file data plus the alt text the author wrote."""

    data: str = Field(min_length=8, max_length=MAX_IMAGE_B64_CHARS)
    alt_text: str | None = Field(default=None, max_length=1000)


class ReviewRequest(BaseModel):
    """Body of POST /api/review. The brand is never taken from the client."""

    text: str = Field(default="", max_length=MAX_REVIEW_CHARS)
    draft_id: str | None = Field(default=None, max_length=100)
    # Answers to ENGANO's earlier questions: question id -> answer.
    answers: dict[str, str] = Field(default_factory=dict, max_length=12)
    images: list[ReviewImage] = Field(default_factory=list, max_length=MAX_IMAGES)

    @field_validator("answers")
    @classmethod
    def _limit_answers(cls, value: dict[str, str]) -> dict[str, str]:
        if any(len(k) > 100 or len(v) > 2000 for k, v in value.items()):
            raise ValueError("An answer is too long.")
        return value

    @model_validator(mode="after")
    def _needs_something_to_review(self) -> "ReviewRequest":
        if not self.text.strip() and not self.images:
            raise ValueError("Add some text or an image to review.")
        return self


class SiteRequest(BaseModel):
    url: str = Field(min_length=3, max_length=2048)


class SiteCheckResponse(BaseModel):
    url: str
    title: str
    screenshot: str
    facts: dict
    design_notes: list[str]
    design_error: str | None
    result: ReviewResult


def _cors_origins() -> list[str]:
    raw = os.getenv("ENGANO_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app(
    review_service: ReviewService | None = None,
    whatsapp_settings: WhatsAppSettings | None = None,
    whatsapp_client: WhatsAppClient | None = None,
    linkedin_settings: LinkedInSettings | None = None,
    linkedin_client: LinkedInClient | None = None,
    linkedin_store: TokenStore | None = None,
    engine_config: EngineConfig | None = None,
    escalation: EscalationSettings | None = None,
    team_store: TeamStore | None = None,
    auth_mirror: AuthMirror | None = None,
    notifier: ReviewerNotifier | None = None,
) -> FastAPI:
    escalation = escalation or EscalationSettings.from_env()
    team_store = team_store or TeamStore(
        os.getenv("ENGANO_DB_PATH") or Path(__file__).resolve().parent.parent / ".data" / "engano.db"
    )
    review_service = review_service or ReviewService(ReviewSettings.from_env())

    whatsapp_settings = whatsapp_settings or WhatsAppSettings.from_env()
    engine_config = engine_config or get_engine_config()
    whatsapp_client = whatsapp_client or WhatsAppClient(
        whatsapp_settings.access_token, whatsapp_settings.graph_version
    )
    for problem in whatsapp_settings.missing():
        log.warning("WhatsApp: %s", problem)

    linkedin_settings = linkedin_settings or LinkedInSettings.from_env()
    linkedin_client = linkedin_client or LinkedInClient(linkedin_settings)
    linkedin_store = linkedin_store or TokenStore(linkedin_settings.token_path)
    if missing := linkedin_settings.missing():
        log.warning("LinkedIn: %s not set; publishing is disabled", ", ".join(missing))

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        await whatsapp_client.aclose()
        await linkedin_client.aclose()

    app = FastAPI(title="ENGANO API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["X-Review-Receipt"],
    )

    async def require_brand_memory_key(
        x_engano_memory_key: str | None = Header(default=None),
    ) -> None:
        configured_key = engine_config.brand_memory_api_key
        if configured_key is None or not configured_key.get_secret_value().strip():
            raise HTTPException(status_code=503, detail="Brand memory API is unavailable.")
        if x_engano_memory_key is None or not secrets.compare_digest(
            x_engano_memory_key,
            configured_key.get_secret_value(),
        ):
            raise HTTPException(status_code=401, detail="Unauthorized.")

    @app.get("/api/health")
    async def health():
        linkedin_token = linkedin_store.load()
        return {
            "status": "ok",
            "brand_id": review_service.settings.brand_id,
            "policy_source": review_service.settings.policy_source,
            "whatsapp_configured": not whatsapp_settings.missing(),
            "linkedin_connected": bool(linkedin_token and not linkedin_token.expired),
        }

    @app.post("/api/review", response_model=ReviewResult)
    async def review(request: ReviewRequest, response: Response, authorization: str | None = Header(default=None)):
        """Run the full multi-agent review on a draft for the configured brand."""
        # A creator signed in to a workspace is also checked against that workspace's own DO/DON'T rules.
        token = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else None
        me = team_store.account_for(token)
        _, rules, scope = team_store.review_scope(me["id"]) if me else (None, [], "")
        try:
            result = await review_service.review_text(
                request.draft_id or f"studio-{uuid.uuid4().hex[:12]}",
                request.text,
                answers=request.answers or None,
                images=[(i.data, i.alt_text) for i in request.images] or None,
                workspace_rules=rules or None,
            )
        except Exception:
            log.exception("Review failed")
            raise HTTPException(status_code=503, detail="Review is unavailable. Try again shortly.")
        # A signed note that ENGANO reviewed exactly this text and found nothing to fix. A creator's
        # submission is only cleared without a human if it carries a valid one.
        clean = (
            result.decision.status.value == "GREEN"
            and not result.questions
            and all(f.severity.value == "low" for f in result.findings)
            and not request.images
        )
        response.headers["X-Review-Receipt"] = team_store.make_receipt(request.text, clean, scope)
        return result

    @app.post("/api/check-website", response_model=SiteCheckResponse)
    async def check_website(request: SiteRequest):
        """Open a public website in a browser; review its text and look; suggest visual changes."""
        try:
            check = await review_service.check_website(request.url)
        except SiteError as exc:
            raise HTTPException(status_code=422, detail=f"Couldn't check that website: {exc}.")
        except Exception:
            log.exception("Website check failed")
            raise HTTPException(status_code=503, detail="Website checks are unavailable. Try again shortly.")
        return check

    # Brand Memory API Endpoints
    @app.get("/api/brand-memory", dependencies=[Depends(require_brand_memory_key)])
    async def get_active_brand_memory():
        try:
            memory = review_service.get_brand_memory()
        except (OSError, RuntimeError, ValueError):
            log.exception("Failed to read active brand memory")
            raise HTTPException(status_code=503, detail="Brand memory storage unavailable.")
        if not memory:
            raise HTTPException(
                status_code=404,
                detail=f"Brand memory not found for active brand '{review_service.settings.brand_id}'.",
            )
        return memory

    @app.get("/api/brand-memory/{brand_id}", dependencies=[Depends(require_brand_memory_key)])
    async def get_brand_memory(brand_id: str):
        try:
            memory = review_service.get_brand_memory(brand_id)
        except (OSError, RuntimeError, ValueError):
            log.exception("Failed to read brand memory")
            raise HTTPException(status_code=503, detail="Brand memory storage unavailable.")
        if not memory:
            raise HTTPException(status_code=404, detail=f"Brand memory for '{brand_id}' not found.")
        return memory

    @app.put("/api/brand-memory", dependencies=[Depends(require_brand_memory_key)])
    async def update_active_brand_memory(updates: Dict[str, Any]):
        try:
            return review_service.update_brand_memory(updates)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Brand '{review_service.settings.brand_id}' not found.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid brand memory update.")
        except (OSError, RuntimeError):
            log.exception("Failed to update active brand memory")
            raise HTTPException(status_code=503, detail="Brand memory storage unavailable.")

    @app.put("/api/brand-memory/{brand_id}", dependencies=[Depends(require_brand_memory_key)])
    async def update_brand_memory(brand_id: str, updates: Dict[str, Any]):
        try:
            return review_service.update_brand_memory(updates, brand_id=brand_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid brand memory update.")
        except (OSError, RuntimeError):
            log.exception("Failed to update brand memory")
            raise HTTPException(status_code=503, detail="Brand memory storage unavailable.")

    @app.post("/api/brand-memory", dependencies=[Depends(require_brand_memory_key)])
    async def create_or_save_brand_memory(memory: BrandMemory):
        try:
            review_service.save_brand_memory(memory)
            return {"status": "saved", "brand_id": memory.brand_id}
        except (OSError, RuntimeError, ValueError):
            log.exception("Failed to persist brand memory")
            raise HTTPException(status_code=503, detail="Brand memory storage unavailable.")

    app.include_router(build_team_router(
            team_store,
            auth_mirror or AuthMirror.from_env(),
            notifier or ReviewerNotifier.from_env(whatsapp_client, whatsapp_settings.graph_version),
        ))
    app.include_router(
        build_whatsapp_router(review_service, whatsapp_settings, whatsapp_client, escalation),
        prefix="/api/webhooks/whatsapp",
    )
    app.include_router(build_linkedin_router(review_service, linkedin_settings, linkedin_client, linkedin_store))
    return app
