# ENGANO Discord adapter

Discord entry point for ENGANO. A gateway bot (discord.py) that sends drafts to `ai_engine` and replies with the decision, cited findings and a suggested rewrite. Runs locally without a public URL.

## Commands

| Command | What it does |
|---|---|
| `/brand-check text:<draft> image:<file>` | Reviews the copy, plus each image's alt text (set it in Discord's attachment description). Image contents aren't analysed yet |
| **Apps → Check brand** (right-click a message) | Reviews that message's text |
| `/engano-help` | Short how-to |

Replies are ephemeral (only the caller sees them): 🟢 ready to publish, 🟡 needs your input (with the engine's question), or 🔴 needs reviewer approval, plus up to 6 findings with their cited rule and fix. A **Request review** button is a placeholder until the studio exists; **Open in studio** appears once `ENGANO_STUDIO_URL` is set.

## Setup

From the repo root (the bot imports `ai_engine` and the shared review service in `Backend/engano_backend` from there):

```
make setup     # installs ai_engine, the backend and this bot into .venv
make discord   # or `make start` for everything
```

Settings in the root `.env` (see `.env.example`):

| Variable | |
|---|---|
| `DISCORD_BOT_TOKEN` | required |
| `ENGANO_BRAND_ID` | brand every Discord draft is checked against, e.g. `nimbus_cloud` |
| `ENGANO_POLICY_SOURCE` | `supabase` (production, `brand_policies` table) or `fixture` (`data/brand_library/*.json`, local testing only) |
| `DISCORD_GUILD_ID` | optional: sync commands to one server instantly while developing |
| `ENGANO_STUDIO_URL` | optional: enables the "Open in studio" button |

`AI_PROVIDER`, `GEMINI_API_KEY`, `SUPABASE_URL` and the other engine settings are read by `ai_engine` from the same `.env`.

## Code

- `engano_discord/bot.py`: commands and reply flow (defers, then reviews off the event loop)
- `Backend/engano_backend/review_service.py`: shared with WhatsApp; picks the policy source and calls `run_brand_review`
- `engano_discord/review.py`: `Draft` → `ReviewInput`, and `ReviewResult` → Discord embed
- `engano_discord/views.py`: buttons under each reply
