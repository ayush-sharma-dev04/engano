# ENGANO backend

The shared core, plus the FastAPI app that hosts the webhook-style channels.

| Path | |
|---|---|
| `engano_backend/review_service.py` | The one bridge to `ai_engine`, used by every channel. Picks the brand (`ENGANO_BRAND_ID`) and policy source (`ENGANO_POLICY_SOURCE`: `supabase`, or `fixture` for local testing) |
| `engano_backend/app.py` | FastAPI app: `/api/health`, and mounts the WhatsApp (`WhatsApp/`) and LinkedIn (`LinkedIn/`) routes |
| `engano_backend/env.py` | Loads the root `.env` |
| `main.py` | Entry point for uvicorn |

Channels live in their own folders: `Discord/`, `WhatsApp/`, `Gmail/` and `LinkedIn/`, each with a README.

| `GET /api/health` | Status, active brand and policy source, whether WhatsApp is configured |
| `GET /api/webhooks/whatsapp` | Meta's webhook verification handshake |
| `POST /api/webhooks/whatsapp` | Incoming WhatsApp messages: review the text, reply in the chat |
| `/api/brand-memory` | Read or manage brand memory; requires `X-Engano-Memory-Key` |

`engano_backend/review_service.py` is the shared bridge to `ai_engine`, used by both this app and the Discord bot. It picks the brand (`ENGANO_BRAND_ID`) and the policy source (`ENGANO_POLICY_SOURCE`: `supabase`, or `fixture` for local testing).

Brand-memory management endpoints are disabled until the backend-only `ENGANO_MEMORY_API_KEY` is configured. Requests must send its value in `X-Engano-Memory-Key`; do not place this key in frontend code. Supabase-backed memory additionally requires the backend-only `SUPABASE_SECRET_KEY`. The Supabase secret bypasses RLS, so it must only be used by this server after its own access checks.

## Run

```
make setup
make backend   # http://localhost:8000 (or `make start` for everything)
make test
```

## Where the data lives

Accounts, workspaces, join codes, assignments, guidelines, drafts, every version of every draft, reviewer
decisions and comments are stored in **Supabase Postgres** (tables from `supabase/migrations`, all with row
level security on and no public policies, so only this backend can read them).

```
make migrate     # creates the tables (safe to run again)
make move-data   # one-off: copies an existing local SQLite file (Backend/.data/engano.db) into Supabase
```

* `SUPABASE_DB_URL` set and `ENGANO_DB_PATH` not set: the backend uses Supabase.
* `ENGANO_DB_PATH=/some/file.db`: the backend uses that SQLite file instead (tests, offline work).
* Neither: a SQLite file at `Backend/.data/engano.db`.

The database is a network hop away, so the backend asks for everything a person may see in one call
(`engano_snapshot`) and keeps recent answers in memory until something is written.

New accounts are also listed under Supabase Authentication → Users (see `auth_mirror.py`, `make sync-auth`).
