import logging
import secrets
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import Depends, FastAPI, Header, HTTPException
from ai_engine.config import EngineConfig, get_engine_config
from ai_engine.schemas.brand_memory import BrandMemory

from engano_linkedin.client import LinkedInClient
from engano_linkedin.config import LinkedInSettings
from engano_linkedin.router import build_router as build_linkedin_router
from engano_linkedin.token_store import TokenStore
from engano_whatsapp.client import WhatsAppClient
from engano_whatsapp.config import WhatsAppSettings
from engano_whatsapp.router import build_router as build_whatsapp_router

from .review_service import ReviewService, ReviewSettings

log = logging.getLogger("engano.backend")


def create_app(
    review_service: ReviewService | None = None,
    whatsapp_settings: WhatsAppSettings | None = None,
    whatsapp_client: WhatsAppClient | None = None,
    linkedin_settings: LinkedInSettings | None = None,
    linkedin_client: LinkedInClient | None = None,
    linkedin_store: TokenStore | None = None,
    engine_config: EngineConfig | None = None,
) -> FastAPI:
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

    app.include_router(
        build_whatsapp_router(review_service, whatsapp_settings, whatsapp_client),
        prefix="/api/webhooks/whatsapp",
    )
    app.include_router(build_linkedin_router(review_service, linkedin_settings, linkedin_client, linkedin_store))
    return app
