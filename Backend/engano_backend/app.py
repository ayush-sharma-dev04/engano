import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
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
) -> FastAPI:
    review_service = review_service or ReviewService(ReviewSettings.from_env())

    whatsapp_settings = whatsapp_settings or WhatsAppSettings.from_env()
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
    @app.get("/api/brand-memory")
    async def get_active_brand_memory():
        memory = review_service.get_brand_memory()
        if not memory:
            raise HTTPException(
                status_code=404,
                detail=f"Brand memory not found for active brand '{review_service.settings.brand_id}'.",
            )
        return memory

    @app.get("/api/brand-memory/{brand_id}")
    async def get_brand_memory(brand_id: str):
        try:
            memory = review_service.get_brand_memory(brand_id)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Storage error: {exc}")
        if not memory:
            raise HTTPException(status_code=404, detail=f"Brand memory for '{brand_id}' not found.")
        return memory

    @app.put("/api/brand-memory")
    async def update_active_brand_memory(updates: Dict[str, Any]):
        try:
            return review_service.update_brand_memory(updates)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Brand '{review_service.settings.brand_id}' not found.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Storage error: {exc}")

    @app.put("/api/brand-memory/{brand_id}")
    async def update_brand_memory(brand_id: str, updates: Dict[str, Any]):
        try:
            return review_service.update_brand_memory(updates, brand_id=brand_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Storage error: {exc}")

    @app.post("/api/brand-memory")
    async def create_or_save_brand_memory(memory: BrandMemory):
        try:
            review_service.save_brand_memory(memory)
            return {"status": "saved", "brand_id": memory.brand_id}
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Failed to persist brand memory: {exc}")

    app.include_router(
        build_whatsapp_router(review_service, whatsapp_settings, whatsapp_client),
        prefix="/api/webhooks/whatsapp",
    )
    app.include_router(build_linkedin_router(review_service, linkedin_settings, linkedin_client, linkedin_store))
    return app
