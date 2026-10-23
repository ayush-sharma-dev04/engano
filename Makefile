# ENGANO dev commands. Run `make help` for the list.
# Needs uv (https://docs.astral.sh/uv/). Secrets come from .env at the repo root.

SHELL := /bin/bash
VENV  := .venv
PY    := $(VENV)/bin/python
PORT  ?= 8000
# Our tunnel's own metrics address, so `make webhook` finds this tunnel and not another cloudflared.
TUNNEL_METRICS := 127.0.0.1:20249

.DEFAULT_GOAL := help
.PHONY: help pull setup start discord backend tunnel webhook web test benchmark clean

help: ## Show this list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

pull: ## Pull the latest commits (fast-forward only, never merges)
	git pull --ff-only

setup: ## Install the AI engine, backend and Discord bot into .venv
	@test -d $(VENV) || uv venv $(VENV)
	uv pip install -q --python $(PY) -r requirements.txt -e ./Backend -e ./Discord

start: setup ## Start everything: Discord bot, backend, tunnel + WhatsApp webhook, web studio (Ctrl+C stops all)
	@trap 'kill $$(jobs -p) 2>/dev/null; wait' INT TERM; \
	$(MAKE) --no-print-directory discord & \
	$(MAKE) --no-print-directory backend & \
	if command -v cloudflared >/dev/null; then \
		$(MAKE) --no-print-directory tunnel & \
		$(PY) Backend/scripts/register_whatsapp_webhook.py --wait --metrics $(TUNNEL_METRICS) --port $(PORT) & \
	else echo "Tunnel: cloudflared not installed, WhatsApp won't receive messages"; fi; \
	if [ -f WebStudio/package.json ]; then $(MAKE) --no-print-directory web & else echo "WebStudio: no package.json yet, skipping"; fi; \
	wait

discord: ## Run the Discord bot (run from the root so it can import ai_engine)
	$(PY) -m engano_discord.bot

backend: ## Run the FastAPI backend on :8000 (PORT=…) (WhatsApp webhook, health check)
	$(PY) -m uvicorn main:app --reload --app-dir Backend --port $(PORT)

tunnel: ## Public HTTPS URL for the backend (then `make webhook`; `make start` does both)
	cloudflared tunnel --no-autoupdate --loglevel warn --metrics $(TUNNEL_METRICS) --url http://localhost:$(PORT)

webhook: ## Point Meta's WhatsApp webhook at the running tunnel (or URL=https://...)
	$(PY) Backend/scripts/register_whatsapp_webhook.py --metrics $(TUNNEL_METRICS) $(if $(URL),--url $(URL))

web: ## Run the web studio dev server (once WebStudio/package.json exists)
	cd WebStudio && npm install && npm run dev

test: setup ## Run the AI engine and backend tests
	$(PY) -m pytest ai_engine/tests Backend/tests -q

benchmark: setup ## Run the AI engine on the Nimbus DB sample draft
	$(PY) ai_engine/benchmark.py

clean: ## Remove virtualenvs and caches
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
