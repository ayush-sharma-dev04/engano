# ENGANO backend

The shared core, plus the FastAPI app that hosts the webhook-style channels.

| Path | |
|---|---|
| `engano_backend/review_service.py` | The one bridge to `ai_engine`, used by every channel. Picks the brand (`ENGANO_BRAND_ID`) and policy source (`ENGANO_POLICY_SOURCE`: `supabase`, or `fixture` for local testing) |
| `engano_backend/app.py` | FastAPI app: `/api/health`, and mounts the WhatsApp (`WhatsApp/`) and LinkedIn (`LinkedIn/`) routes |
| `engano_backend/env.py` | Loads the root `.env` |
| `main.py` | Entry point for uvicorn |

Channels live in their own folders: `Discord/`, `WhatsApp/`, `Gmail/` and `LinkedIn/`, each with a README.

```
make setup
make backend   # http://localhost:8000 (or `make start` for everything)
make test
```
