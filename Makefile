# ENGANO dev commands. Run `make help` for the list.
# Needs uv (https://docs.astral.sh/uv/). Secrets come from .env at the repo root.

SHELL := /bin/bash
VENV  := .venv
PY    := $(VENV)/bin/python
PORT  ?= 8000
# Our tunnel's own metrics address, so `make webhook` finds this tunnel and not another cloudflared.
TUNNEL_METRICS := 127.0.0.1:20249
# Local AI settings, read from .env so `make start` knows whether to run Ollama.
AI_PROVIDER  := $(shell sed -n 's/^AI_PROVIDER=//p' .env 2>/dev/null)
OLLAMA_MODEL := $(or $(shell sed -n 's/^OLLAMA_MODEL=//p' .env 2>/dev/null),qwen2.5vl:3b)
OLLAMA_URL   := http://localhost:11434

.DEFAULT_GOAL := help
.PHONY: deploy api-url help pull setup renderer renderer-up migrate migrate-status seed start ollama discord backend gmail tunnel webhook linkedin web test benchmark clean

help: ## Show this list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

pull: ## Pull the latest commits (fast-forward only, never merges)
	git pull --ff-only

CHANNELS := Discord WhatsApp Gmail LinkedIn

setup: ## Install the AI engine, backend and every channel into .venv
	@test -d $(VENV) || uv venv $(VENV)
	uv pip install -q --python $(PY) -r requirements.txt -e ./Backend $(foreach c,$(CHANNELS),-e ./$(c))

RENDERER_IMAGE := engano-renderer
RENDERER_PORT  ?= 8090
RENDERER_URL   := $(shell sed -n 's/^ENGANO_RENDERER_URL=//p' .env 2>/dev/null)

renderer: ## Build and start the website-check browser in Docker (listens on 127.0.0.1:8090 only)
	docker build -q -f Renderer/Dockerfile -t $(RENDERER_IMAGE) .
	-docker rm -f engano-renderer >/dev/null 2>&1
	docker run -d --name engano-renderer --restart unless-stopped \
		-p 127.0.0.1:$(RENDERER_PORT):8090 --init --shm-size=1g --memory=2g --pids-limit=512 \
		--cap-drop=ALL --security-opt=no-new-privileges --read-only --tmpfs /tmp:rw,size=512m -e HOME=/tmp \
		$(RENDERER_IMAGE) >/dev/null
	@echo "Renderer up on http://127.0.0.1:$(RENDERER_PORT). Put ENGANO_RENDERER_URL=http://127.0.0.1:$(RENDERER_PORT) in .env"

renderer-up: ## Start the website-check browser if it already exists, else build it
	@docker start engano-renderer >/dev/null 2>&1 || $(MAKE) --no-print-directory renderer

migrate: setup ## Apply new supabase/migrations/*.sql to the database (needs SUPABASE_DB_URL in .env)
	$(PY) supabase/migrate.py

migrate-status: setup ## Show which migrations are applied and which are pending
	$(PY) supabase/migrate.py --status

seed: setup ## Load brand rules from data/brand_library/*.json into the database (APPLY=1 to write; default is a dry run)
	$(PY) supabase/seed.py $(if $(APPLY),--apply)

move-data: setup ## Copy accounts, workspaces and drafts from the local SQLite file into Supabase (run `make migrate` first)
	$(PY) -m engano_backend.move_to_supabase

sync-auth: setup ## List every ENGANO account under Supabase Authentication → Users (needs SUPABASE_SECRET_KEY in .env)
	$(PY) -m engano_backend.sync_auth

demo: ## Serve the demo video page at http://127.0.0.1:8765/ (Ctrl+C stops it)
	python3 docs/demo/serve.py docs/demo 8765

start: setup ## Start everything: Ollama (if AI_PROVIDER=ollama), backend, Discord, Gmail, tunnel + webhook (Ctrl+C stops all)
	@trap 'kill $$(jobs -p) 2>/dev/null; wait' INT TERM; \
	if [ "$(AI_PROVIDER)" = ollama ]; then $(MAKE) --no-print-directory ollama & fi; \
	if [ -n "$(RENDERER_URL)" ] && command -v docker >/dev/null; then $(MAKE) --no-print-directory renderer-up & fi; \
	$(MAKE) --no-print-directory discord & \
	$(MAKE) --no-print-directory backend & \
	$(MAKE) --no-print-directory gmail & \
	if command -v cloudflared >/dev/null; then \
		$(MAKE) --no-print-directory tunnel & \
		$(PY) -m engano_whatsapp.register_webhook --wait --metrics $(TUNNEL_METRICS) --port $(PORT) & \
		$(PY) -m engano_backend.public_url --wait --metrics $(TUNNEL_METRICS) & \
	else echo "Tunnel: cloudflared not installed, WhatsApp won't receive messages"; fi; \
	if [ -f Frontend/package.json ]; then $(MAKE) --no-print-directory web & else echo "Frontend: no package.json, skipping"; fi; \
	wait

ollama: ## Run the local AI model (Ollama): start the server, download the model if missing, load it
	@if curl -sf -m 1 $(OLLAMA_URL)/api/version >/dev/null; then \
		echo "Ollama: already running"; \
	else \
		OLLAMA_KEEP_ALIVE=1h ollama serve >/dev/null 2>&1 & \
		until curl -sf -m 1 $(OLLAMA_URL)/api/version >/dev/null; do sleep 0.5; done; \
	fi; \
	ollama list | grep -q "^$(OLLAMA_MODEL) " || ollama pull $(OLLAMA_MODEL); \
	curl -sf $(OLLAMA_URL)/api/generate -d '{"model":"$(OLLAMA_MODEL)","keep_alive":"1h"}' >/dev/null \
		&& echo "Ollama: $(OLLAMA_MODEL) loaded (on $$(ollama ps | grep -oE '[0-9/%]+ (CPU|GPU)[/A-Z]*' | head -1))"; \
	wait

discord: ## Run the Discord bot (run from the root so it can import ai_engine)
	$(PY) -m engano_discord.bot

backend: ## Run the FastAPI backend on :8000 (WhatsApp webhook, LinkedIn routes, health)
	$(PY) -m uvicorn main:app --reload --app-dir Backend --port $(PORT)

gmail: ## Run the Gmail review inbox (checks for new email every 15 s)
	$(PY) -m engano_gmail

linkedin: ## Connect a LinkedIn account (opens the sign-in page; backend must be running)
	xdg-open http://localhost:$(PORT)/api/oauth/linkedin/start

tunnel: ## Public HTTPS URL for the backend (then `make webhook`; `make start` does both)
	cloudflared tunnel --no-autoupdate --loglevel warn --metrics $(TUNNEL_METRICS) --url http://localhost:$(PORT)

deploy: ## Build the web app with the backend address from .env (VITE_API_URL, else the running tunnel) and publish it to Netlify
	$(PY) -m engano_backend.deploy_site

api-url: ## Show the backend's public address and the link that points the hosted site at it
	$(PY) -m engano_backend.public_url --metrics $(TUNNEL_METRICS)

webhook: ## Point Meta's WhatsApp webhook at the running tunnel (or URL=https://...)
	$(PY) -m engano_whatsapp.register_webhook --metrics $(TUNNEL_METRICS) $(if $(URL),--url $(URL))

web: ## Run the web studio dev server (once Frontend/package.json exists)
	cd Frontend && npm install && npm run dev

test: setup ## Run the AI engine and channel tests
	$(PY) -m pytest ai_engine/tests $(foreach c,$(CHANNELS),$(wildcard $(c)/tests)) -q

benchmark: setup ## Run the AI engine on the Nimbus DB sample draft
	$(PY) ai_engine/benchmark.py

clean: ## Remove virtualenvs and caches
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
