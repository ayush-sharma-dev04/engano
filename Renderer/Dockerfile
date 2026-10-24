# The website-check browser. Chromium runs in here, not on your machine, and only ever
# reaches the public internet (through safe_proxy, which refuses private addresses).
# Build from the repo root:  docker build -f Renderer/Dockerfile -t engano-renderer .
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    ENGANO_RENDERER_NO_SANDBOX=1

RUN pip install "playwright>=1.49,<2" "fastapi>=0.115" "uvicorn>=0.32" "httpx>=0.28" \
 && playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/* \
 && chmod -R a+rX /ms-playwright

RUN useradd --create-home --uid 10001 renderer
WORKDIR /app
COPY Backend/engano_backend/__init__.py Backend/engano_backend/website.py Backend/engano_backend/safe_proxy.py Backend/engano_backend/site_render.py engano_backend/
COPY Renderer/renderer_app.py .

USER renderer
EXPOSE 8090
CMD ["python", "-m", "uvicorn", "renderer_app:app", "--host", "0.0.0.0", "--port", "8090"]
