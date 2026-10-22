import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .review_service import ReviewService, ReviewSettings
from .whatsapp.client import WhatsAppClient
from .whatsapp.config import WhatsAppSettings
from .whatsapp.router import build_router as build_whatsapp_router

log = logging.getLogger("engano.backend")


def create_app(
    review_service: ReviewService | None = None,
    whatsapp_settings: WhatsAppSettings | None = None,
    whatsapp_client: WhatsAppClient | None = None,
) -> FastAPI:
    review_service = review_service or ReviewService(ReviewSettings.from_env())
    whatsapp_settings = whatsapp_settings or WhatsAppSettings.from_env()
    whatsapp_client = whatsapp_client or WhatsAppClient(
        whatsapp_settings.access_token, whatsapp_settings.graph_version
    )
    for problem in whatsapp_settings.missing():
        log.warning("WhatsApp: %s", problem)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        await whatsapp_client.aclose()

    app = FastAPI(title="ENGANO API", version="0.1.0", lifespan=lifespan)

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "brand_id": review_service.settings.brand_id,
            "policy_source": review_service.settings.policy_source,
            "whatsapp_configured": not whatsapp_settings.missing(),
        }

    app.include_router(
        build_whatsapp_router(review_service, whatsapp_settings, whatsapp_client),
        prefix="/api/webhooks/whatsapp",
    )
    return app
