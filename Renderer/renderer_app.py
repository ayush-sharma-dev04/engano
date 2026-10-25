"""HTTP front door of the website-check browser container.

POST /render {"url": "https://..."} -> page text, screenshots (base64 PNG) and measured facts.
Run it with `make renderer`; the backend finds it through ENGANO_RENDERER_URL.
"""

import base64
import os
import secrets

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from engano_backend.site_render import render_site
from engano_backend.website import SiteError

TOKEN = os.getenv("ENGANO_RENDERER_TOKEN", "")

app = FastAPI(title="ENGANO renderer", docs_url=None, redoc_url=None, openapi_url=None)


class RenderRequest(BaseModel):
    url: str = Field(min_length=3, max_length=2048)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/render")
async def render(request: RenderRequest, x_renderer_token: str | None = Header(default=None)):
    if TOKEN and not (x_renderer_token and secrets.compare_digest(x_renderer_token, TOKEN)):
        raise HTTPException(status_code=401, detail="Unauthorized.")
    try:
        site = await render_site(request.url)
    except SiteError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "final_url": site.final_url,
        "title": site.title,
        "text": site.text,
        "screenshots": [base64.b64encode(png).decode() for png in site.screenshots],
        "facts": site.facts,
    }
