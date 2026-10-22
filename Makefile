# ENGANO dev commands. Run `make help` for the list.
# Needs uv (https://docs.astral.sh/uv/). Secrets come from .env at the repo root.

SHELL := /bin/bash
VENV  := .venv
PY    := $(VENV)/bin/python
PORT  ?= 8000

.DEFAULT_GOAL := help
.PHONY: help pull setup start discord backend tunnel web test benchmark clean

help: ## Show this list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

pull: ## Pull the latest commits (fast-forward only, never merges)
	git pull --ff-only

setup: ## Install the AI engine, backend and Discord bot into .venv
	@test -d $(VENV) || uv venv $(VENV)
	uv pip install -q --python $(PY) -r requirements.txt -e ./Backend -e ./Discord

start: setup ## Start every service that exists (Ctrl+C stops all)
	@trap 'kill $$(jobs -p) 2>/dev/null; wait' INT TERM; \
	$(MAKE) --no-print-directory discord & \
	if [ -f Backend/main.py ]; then $(MAKE) --no-print-directory backend & else echo "Backend: no Backend/main.py yet, skipping"; fi; \
	if [ -f WebStudio/package.json ]; then $(MAKE) --no-print-directory web & else echo "WebStudio: no package.json yet, skipping"; fi; \
	wait

discord: ## Run the Discord bot (run from the root so it can import ai_engine)
	$(PY) -m engano_discord.bot

backend: ## Run the FastAPI backend on :8000 (PORT=…) (WhatsApp webhook, health check)
	$(PY) -m uvicorn main:app --reload --app-dir Backend --port $(PORT)

tunnel: ## Public HTTPS URL for the backend (paste <url>/api/webhooks/whatsapp into Meta)
	cloudflared tunnel --url http://localhost:$(PORT)

web: ## Run the web studio dev server (once WebStudio/package.json exists)
	cd WebStudio && npm install && npm run dev

test: setup ## Run the AI engine and backend tests
	$(PY) -m pytest ai_engine/tests Backend/tests -q

benchmark: setup ## Run the AI engine on the Nimbus DB sample draft
	$(PY) ai_engine/benchmark.py

clean: ## Remove virtualenvs and caches
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
