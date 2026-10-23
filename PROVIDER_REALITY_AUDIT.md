# ENGANO — Provider Reality Audit & Backend Hardening Report

**Date:** 2026-10-23  
**Auditor:** Senior AI Systems Engineer & Backend Architect  
**Workspace:** `Projects/engano` (Branch: `main`)  
**Skills & Tools Executed:** Ponytail (`/home/ayush/.gemini/config/plugins/ponytail/skills/ponytail/SKILL.md`), Graphify CLI (`/home/ayush/.local/bin/graphify`), Pytest (`.venv/bin/pytest`)

---

## 1. Executive Summary & Reality Audit

An evidence-based audit was performed on the real code paths, external cloud LLM connections, local Ollama daemon, deterministic rule evaluators, brand memory persistence, and fix-cum-rewrite pipeline.

Earlier reports claimed that all 85 tests passed and that multi-agent LLM review was operational. Our audit revealed critical discrepancies between mocked claims and production reality:

1. **Gemini Production Breakdown:**
   - The previous default model `gemini-2.5-flash` in `ai_engine/config.py` was **retired by Google** and returned `HTTP 404 NOT_FOUND` ("This model models/gemini-2.5-flash is no longer available to new users").
   - Unit tests passed previously only because tests were either mocked or ran with offline fixtures. When executed against `.env` with `AI_PROVIDER=gemini`, the review pipeline crashed with `RuntimeError: Gemini API Error: 404 NOT_FOUND`, causing WhatsApp clean-draft tests and multi-agent pipeline tests to fail.
   - The recommended `gemini-3.8-flash` is operational but experiences temporary Google server-side demand spikes (`HTTP 503 UNAVAILABLE`) and higher latency (~35s).
   - In contrast, `gemini-3.1-flash-lite` is fully operational, responsive (~1.6s latency), and compliant with the Google GenAI SDK.
   - **Remediation:** Updated configuration to default to `gemini-3.8-flash` with automatic, resilient fallback to `gemini-3.1-flash-lite` if Google returns 503/404, preventing review failures during cloud API spikes.

2. **Ollama & Local Qwen 2.5 VL 3B Verified:**
   - The local Ollama daemon is active at `http://localhost:11434` (`systemctl status ollama`).
   - The configured model `qwen2.5vl:3b` is genuinely installed on this machine (`3.2 GB`, verified via `ollama list`).
   - Real inference requests executed successfully via `/api/generate` with `"format": "json"`, returning structured findings in ~7.9s.

3. **Deterministic Rules (`rules_only`) Verified:**
   - `AI_PROVIDER=rules_only` executes 100% offline with 0.0ms external latency and zero cloud/local model calls.
   - Deterministic rule suites for terminology, claims, SLA facts, legal disclaimers, and accessibility execute reliably.

4. **Persistent Brand Memory Implemented:**
   - Real persistence layer implemented via `FileBrandMemoryStore` in `data/brand_memory/{brand_id}.json` that survives backend restarts across sessions.
   - Supabase reality checked: Querying `https://yddyixcrejecxicojijr.supabase.co/rest/v1/brand_memory` returned `HTTP 404 PGRST205` ("Could not find the table 'public.brand_memory' in the schema cache"). The database lacks migrations, and the anon key cannot perform DDL. Explicit error handling was added without masking.
   - Brand isolation and Rule Supremacy enforced: Brand memory NEVER overrides authoritative `BrandPolicy` rules.

5. **Fix-cum-Rewrite Workflow Hardened:**
   - Implemented bounded 1-pass minimal correction with full post-rewrite revalidation across all rule domains.
   - Strict decision safety enforced: A rewrite proposal **never overrides or bypasses a RED decision**. Unfixable critical claims remain RED requiring human reviewer approval.

---

## 2. Evidence-Based Capability Matrix

| Capability | Status | Evidence & Test Command | Observed Outcome | Limitations / Blockers |
| :--- | :--- | :--- | :--- | :--- |
| **Gemini Provider** | **VERIFIED** | `PYTHONPATH=.:Backend .venv/bin/pytest ai_engine/tests/test_providers_reality.py::test_real_gemini_invocation_end_to_end` | Real Google GenAI SDK invocation returned 200 OK (`gemini-3.1-flash-lite` in 1.6s; `gemini-3.8-flash` in 35s). | `gemini-2.5-flash` is retired (404). `gemini-3.8-flash` has occasional 503 high-demand spikes. |
| **Ollama / Qwen Provider** | **VERIFIED** | `PYTHONPATH=.:Backend .venv/bin/pytest ai_engine/tests/test_providers_reality.py::test_real_ollama_invocation_end_to_end` | Live inference to `http://localhost:11434` with model `qwen2.5vl:3b` returned parsed findings in 7.9s. | Requires Ollama daemon running locally. |
| **Rules-Only Provider** | **VERIFIED** | `PYTHONPATH=.:Backend .venv/bin/pytest ai_engine/tests/test_providers_reality.py::test_rules_only_execution_independent_of_cloud_and_local` | 100% offline, zero network requests, latency 0.0ms. | Evaluates deterministic rules only; semantic nuance requires LLM. |
| **Provider Selection & Switching** | **VERIFIED** | `PYTHONPATH=.:Backend .venv/bin/pytest ai_engine/tests/test_providers_reality.py::test_coordinator_provider_runtime_switching` | Factory and `CoordinatorAgent` correctly switch between `rules_only`, `gemini`, `ollama`. Invalid names reject with `ValueError`. | Switching via `.env` requires backend reload. |
| **Multi-Agent Pipeline** | **VERIFIED** | `PYTHONPATH=.:Backend .venv/bin/pytest ai_engine/tests/test_multi_agent_pipeline.py` | Full 4-stage pipeline dispatches `RulesSpecialist`, `ToneSpecialist`, `ClaimsSpecialist`, `VisualWCAGSpecialist`, `LegalPolicySpecialist`. | All 18 criteria verified. |
| **Fix-cum-Rewrite & Revalidation** | **VERIFIED** | `PYTHONPATH=.:Backend .venv/bin/pytest ai_engine/tests/test_fix_cum_rewrite.py` | Minimal corrections applied, post-revalidation executed; RED decision strictly cannot be bypassed. Clean drafts produce no rewrite. | Rewriter does not hallucinate facts; unfixable claims require reviewer approval. |
| **Persistent Brand Memory** | **VERIFIED** | `PYTHONPATH=.:Backend .venv/bin/pytest ai_engine/tests/test_brand_memory.py` | File-backed storage in `data/brand_memory/{brand_id}.json` survives reboots; FastAPI `GET`/`PUT` endpoints verified; brand isolation verified. | Supabase table `public.brand_memory` not migrated on remote server (HTTP 404). |
| **Specialist Failure Handling** | **VERIFIED** | `PYTHONPATH=.:Backend .venv/bin/pytest ai_engine/tests/test_multi_agent_pipeline.py::test_criterion_13_specialist_failure_fails_closed` | Specialist failure creates high-severity finding; fails closed and never generates false GREEN. | Safe fallback optionally available via `SAFE_FALLBACK=true`. |

---

## 3. Deep-Dive Provider Audit

### 3.1 Gemini Cloud Provider

- **Configuration:** `AI_PROVIDER=gemini`, `GEMINI_API_KEY=<configured in .env>`, `GEMINI_MODEL=gemini-3.8-flash`.
- **Credential Handling:** Read into Pydantic `SecretStr`. Masked from `repr()`, logs, and API responses.
- **Model Realities Discovered:**
  - `gemini-2.5-flash`: Retired by Google (`404 NOT_FOUND. 'This model models/gemini-2.5-flash is no longer available to new users'`).
  - `gemini-3.8-flash`: Active Google model. Operational, but experiences periodic `503 UNAVAILABLE` spikes due to high demand.
  - `gemini-3.1-flash-lite`: Active Google model. Responded with `GEMINI_LIVE_OK` in 1.6s.
- **Resilience Enhancement:**
  In `ai_engine/providers/gemini.py`, if Google returns `503 UNAVAILABLE` or `404 NOT_FOUND` on the primary model, the provider automatically attempts fallback to `gemini-3.1-flash-lite`.
- **Validation:** Live end-to-end integration test `test_real_gemini_invocation_end_to_end` passed.

### 3.2 Local Ollama & Qwen 2.5 VL 3B

- **Configuration:** `AI_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://localhost:11434`, `OLLAMA_MODEL=qwen2.5vl:3b`.
- **Daemon Verification:**
  ```bash
  systemctl status ollama
  # Active: active (running)
  ollama list
  # NAME            ID              SIZE      MODIFIED
  # qwen2.5vl:3b    fb90415cde1e    3.2 GB    3 days ago
  ```
- **Inference Verification:**
  Direct curl to `http://localhost:11434/api/generate` returned `"response":"OK"` in 6.1s.
  Full review call using `OllamaProvider.review()` parsed structured JSON findings in 7.9s with 0 cloud data leakage.
- **Validation:** Live integration test `test_real_ollama_invocation_end_to_end` passed.

### 3.3 Deterministic Rules (`rules_only`)

- **Configuration:** `AI_PROVIDER=rules_only`.
- **Behavior:** No sockets opened, no HTTP clients initialized, zero cloud or local inference.
- **Rules Executed:**
  - `evaluate_terminology`: Prohibited product variants (`NimbusDB`, `Nimbus-DB`) mapped to `Nimbus DB`.
  - `evaluate_claims`: Superlative benchmark requirements (`Rule 4.2`), prohibited guarantees (`100% uptime`).
  - `evaluate_factual`: Active SLA dates and approved facts (`fact_sla_uptime`).
  - `LegalPolicySpecialist`: Missing mandatory disclaimers and restricted claims.
  - `VisualWCAGSpecialist`: Contrast ratio thresholds (4.5:1 / 3:1) and alt-text presence.
- **Validation:** Tested independently and offline across all test suites.

---

## 4. Fix-Cum-Rewrite Architecture & Decision Safety

Our implemented workflow strictly enforces:

$$\text{Review} \longrightarrow \text{Findings} \longrightarrow \text{Minimal Fix} \longrightarrow \text{Post-Rewrite Revalidation} \longrightarrow \text{Final Outcome}$$

### Key Safety Guarantees

1. **RED Decision Supremacy:**
   If a draft contains a prohibited claim (e.g. `100% uptime`), the decision is `RED` (`ActionRequiredBy.REVIEWER_APPROVAL`). Even if the rewrite proposes fixing mechanical items, `result.decision.status` **strictly remains RED**. A rewrite agent cannot approve an uncompliant draft.
2. **Post-Rewrite Revalidation:**
   The proposed copy is re-evaluated across the complete rule suite (terminology, claims, factual, tone, legal).
3. **Traceability:**
   `ReviewResult` provides:
   - `original_text`: The untouched draft copy.
   - `findings`: Detected original violations.
   - `proposed_rewrite`: The minimally repaired copy (or `None` if clean).
   - `post_rewrite_findings`: Any findings remaining or introduced in the rewrite.
   - `rewrite_proposal`: Full metadata including `applied_fixes`, `is_post_revalidation_passed`, and `post_revalidation_decision`.
4. **Meta-Instruction Protection:**
   The rewriter filters out meta-instructions (e.g. "Rephrase in a clear tone", "Remove or replace claim") so they are never erroneously substituted as literal draft copy.

---

## 5. Persistent Brand Memory Implementation

### Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                       BrandMemory Store                         │
├────────────────────────────────┬────────────────────────────────┤
│      FileBrandMemoryStore      │    SupabaseBrandMemoryStore    │
│  data/brand_memory/<id>.json   │     /rest/v1/brand_memory      │
│  (Persistent across reboots)   │  (Production PostgREST RLS)    │
└────────────────────────────────┴────────────────────────────────┘
                               ▲
                               │
             ┌─────────────────┴─────────────────┐
             │       ReviewService & API         │
             │   GET /api/brand-memory           │
             │   PUT /api/brand-memory           │
             └─────────────────┬─────────────────┘
                               │ Context
                               ▼
                 Authoritative BrandPolicy
               (NEVER overridden by Memory)
```

1. **Persistence:** Saved in `data/brand_memory/{brand_id}.json`. Survives backend process restarts.
2. **Brand Isolation:** Scoped strictly by `brand_id`. Brand Alpha cannot read or modify Brand Beta.
3. **Rule Supremacy:** Brand memory stores identity, voice preferences, target audience, and approved claims. However, if a rule in `BrandPolicy` prohibits an action (e.g. "100% uptime"), brand memory containing that claim can **never override the policy rule**.
4. **Supabase Reality:**
   - Attempting to query `brand_memory` or `brand_policies` on the configured Supabase instance returns `HTTP 404 PGRST205` because tables have not been created in the public schema.
   - The application does not pretend Supabase memory loaded; it raises an explicit error if `ENGANO_MEMORY_SOURCE=supabase` is requested while tables are missing.
   - `FileBrandMemoryStore` is the active, verified persistent storage when `ENGANO_POLICY_SOURCE=fixture`.

---

## 6. Exact Steps for Runtime Provider Switching

### Step 1: Run with Google Gemini
1. Ensure `.env` has:
   ```dotenv
   AI_PROVIDER=gemini
   GEMINI_MODEL=gemini-3.8-flash
   # GEMINI_API_KEY is read from .env
   ```
2. Start the backend:
   ```bash
   uvicorn engano_backend.app:create_app --factory --host 0.0.0.0 --port 8000
   ```
3. Test a draft:
   ```bash
   curl -X POST http://localhost:8000/api/webhooks/whatsapp \
     -H "Content-Type: application/json" \
     -d '{"object":"whatsapp_business_account","entry":[{"changes":[{"value":{"messages":[{"id":"w1","from":"123","type":"text","text":{"body":"Nimbus DB provides high performance cloud databases."}}]}}]}]}'
   ```

### Step 2: Run with Local Ollama (Qwen 2.5 VL 3B)
1. Edit `.env`:
   ```dotenv
   AI_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=qwen2.5vl:3b
   ```
2. Restart backend:
   ```bash
   uvicorn engano_backend.app:create_app --factory --host 0.0.0.0 --port 8000
   ```
3. Reviews are processed through the local Qwen model with 0 cloud data transfer.

### Step 3: Run with Deterministic Rules Only
1. Edit `.env`:
   ```dotenv
   AI_PROVIDER=rules_only
   ```
2. Restart backend.
3. Reviews execute instantaneously (0.0ms latency) without requiring Gemini credentials or Ollama service.

---

## 7. Test Results Summary

Complete test suite execution command:
```bash
PYTHONPATH=.:Backend .venv/bin/pytest -v
```

**Results:**
- Total tests collected: 108
- **Passed: 108**
- **Failed: 0**
- Warnings: 2 (standard library deprecation notices for starlette testclient & python 3.14 union types)

All 85 legacy tests plus 23 new regression tests for providers, brand memory, and fix-cum-rewrite passed cleanly.
