# Engano AI/ML Review Engine

The Engano AI/ML Review Engine provides brand governance and copy review for marketing and product drafts in Web Studio. It pairs deterministic Python rules with semantic LLM evaluation (Google Gemini and local Ollama) in a bounded, multi-agent pipeline.

---

## 1. Engine Architecture

```
[Web Studio / FastAPI Backend]
               │
               ▼
   run_brand_review(request)
               │
               ▼
     [Review Orchestrator]
       ├── 1. Authoritative Policy Retrieval (Supabase / Mock Repository)
       ├── 2. Policy Analysis Agent (Scope & applicability mapping)
       ├── 3. Deterministic Evaluator (Terminology, Claims, Factual, WCAG)
       ├── 4. Semantic Provider (Rules-Only / Ollama qwen2.5vl:3b / Gemini)
       ├── 5. Evidence Validation Agent (Verified, Unsupported, Contradicted)
       ├── 6. Finding Consolidation & Text Span Verification
       ├── 7. Decision Router (RED > YELLOW > GREEN with Strict Mode)
       └── 8. Safe Rewrite Agent (Minimal, non-hallucinating corrections)
```

### Deterministic vs. Semantic Synergy
1. **Deterministic Rules First**: Syntax, product spelling, prohibited variants, absolute uptime SLAs, retired offer dates, and measured WCAG contrast thresholds are evaluated deterministically in Python. This guarantees sub-millisecond detection of known violations without LLM hallucinations.
2. **Semantic Review Layer**: When enabled, Google Gemini or local Ollama analyzes complex nuances, subjective tone mismatches, and indirect claims.
3. **Safe Consolidation**: Findings are unified, text spans verified against original text, and duplicate overlapping findings deduplicated keeping the highest severity.

---

## 2. Module Responsibilities

| Module | Responsibility |
|---|---|
| `ai_engine/config.py` | Central Pydantic Settings configuration (`AI_PROVIDER`, model names, timeouts, credentials, secret masking). |
| `ai_engine/review.py` | Stable public function `run_brand_review(...)` imported by backend callers. |
| `ai_engine/schemas/` | Pydantic v2 data models for `ReviewInput`, `ReviewResult`, `Finding`, `TextSpan`, and `BrandPolicy`. |
| `ai_engine/providers/base.py` | Abstract `BaseProvider` contract and `ProviderResponse` envelope. |
| `ai_engine/providers/gemini.py` | Google Gen AI SDK integration with structured outputs and error handling. |
| `ai_engine/providers/ollama.py` | Local Ollama integration for model `qwen2.5vl:3b` via HTTP PostgREST/JSON. |
| `ai_engine/providers/factory.py` | Provider instantiation (`rules_only`, `gemini`, `ollama`, `auto`). |
| `ai_engine/rules/terminology.py` | Word-boundary-safe terminology checks for prohibited brand variants. |
| `ai_engine/rules/claims.py` | Superlative, guarantee, and uptime claim checks with benchmark verification. |
| `ai_engine/rules/factual.py` | SLA facts, offer validity dates, and retired offer contradictions. |
| `ai_engine/rules/accessibility.py` | Deterministic WCAG contrast (4.5:1, 3:1) and missing alt-text checks on visual metadata. |
| `ai_engine/rules/evaluator.py` | Deterministic pipeline coordinator and span-aware deduplicator. |
| `ai_engine/agents/policy_analysis.py` | Analyzes which authoritative policy provisions apply to submitted draft text. |
| `ai_engine/agents/evidence_validation.py` | Classifies claims into `verified`, `unsupported`, `contradicted`, or `unverified_provided`. |
| `ai_engine/agents/rewrite.py` | Proposes minimal safe corrections without fabricating benchmarks or statistics. |
| `ai_engine/agents/governance.py` | Analyzes finding trends and proposes human-reviewed policy adjustments without database mutation. |
| `ai_engine/agents/orchestrator.py` | Complete bounded review lifecycle coordinator. |
| `ai_engine/integrations/supabase_policy_repository.py` | Repository boundary isolating production Supabase queries from offline test mocks. |
| `ai_engine/benchmark.py` | Local execution benchmark against the Nimbus Cloud test fixture. |

---

## 3. Supported Provider Modes

- `rules_only` (Default / Offline): Executes deterministic evaluators only. Never initiates outbound HTTP requests or accesses LLMs.
- `ollama`: Invokes the local Ollama instance (`http://localhost:11434`) running `qwen2.5vl:3b`. Local only; no cloud transmission.
- `gemini`: Uses Google Gemini (via `google-genai` SDK) with configurable model (`gemini-2.5-flash`). Requires `GEMINI_API_KEY`.
- `auto`: Intelligently detects whether local Ollama is active; falls back to Gemini if configured, or rules-only if offline.

---

## 4. Setup and Environment (Linux / Fedora)

### Prerequisites
- Python 3.12+ (tested on Python 3.14.8)
- Optional: Local Ollama with `qwen2.5vl:3b` installed

### Virtual Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment Configuration
Copy `.env.example` to `.env` and set active provider:
```bash
cp .env.example .env
```
Example `.env`:
```dotenv
AI_PROVIDER=rules_only
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5vl:3b
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
REQUEST_TIMEOUT_SECONDS=30.0
STRICT_MODE=false
```

---

## 5. Running Reviews and Benchmarks

### Running the Public Entry Point in Code
```python
from ai_engine.review import run_brand_review
from ai_engine.schemas import ReviewInput
from ai_engine.integrations import MockPolicyRepository

# Using Mock/Test repository:
repo = MockPolicyRepository()
repo.load_fixture("data/brand_library/nimbus_db.json")

request = ReviewInput(
    draft_id="draft_100",
    brand_id="nimbus_cloud",
    content_text="NimbusDB is the fastest database in the world, with 100% uptime. Try it free forever!",
)

result = run_brand_review(request=request, repository=repo)
print("Decision:", result.decision.status)  # RED
print("Findings:", len(result.findings))     # 4 findings
print("Rewrite:", result.proposed_rewrite)
```

### Running the Local Benchmark
```bash
# Fast offline rules_only benchmark
python ai_engine/benchmark.py

# Local Ollama benchmark (requires local ollama running qwen2.5vl:3b)
python ai_engine/benchmark.py --provider ollama
```

### Running Offline Automated Tests
```bash
pytest ai_engine/tests/ -v
```

---

## 6. Schemas and Evidence Classification

### Evidence Status
- `verified`: Directly substantiated by authoritative brand policy or approved benchmark.
- `unsupported`: Claim makes an affirmative assertion without an applicable source citation.
- `contradicted`: Directly conflicts with an authoritative brand SLA, fact, or retired offer.
- `unverified_provided`: Creator supplied custom evidence that has not been independently verified.

### Decision Precedence
`RED > YELLOW > GREEN`

- **RED**: Triggered by critical severity, direct factual contradictions, retired offers, or material unsupported claims. Requires `reviewer_approval`.
- **YELLOW**: Triggered by ambiguity, unverified creator evidence, or unresolved medium findings under `strict_mode=True`. Requires `creator_clarification`.
- **GREEN**: Draft is compliant. Minor mechanical fixes (e.g. terminology) may provide `creator_one_click_correction` without blocking publication.

---

## 7. Supabase Production Integration

### Integration Boundary
The engine connects through `BasePolicyRepository`.
- **`MockPolicyRepository`**: Used in unit tests and local development.
- **`SupabasePolicyRepository`**: Used in production. Connects to Supabase via authenticated REST client.
- **Fail-Safe Rule**: If Supabase connectivity fails or credentials are not configured, the engine returns an **operational failure** or **incomplete policy status**. It **never** silently falls back to the Nimbus fixture in production.

### Information Needed from Supabase Team to Finalize Production Link
To complete live Supabase connectivity, the other team must provide:
1. Target table name (e.g., `brand_policies`).
2. Confirmed schema fields:
   - `brand_id`: string/uuid identifier (primary key).
   - `brand_name`: string.
   - `approved_terminology`: JSON array of `{term_id, approved_term, prohibited_variants, replacement_suggestion, case_sensitive}`.
   - `claims_policy`: JSON object containing `{superlatives_require_benchmark, rule_reference, superlative_patterns, forbidden_guarantees, permitted_benchmarks}`.
   - `factual_rules`: JSON array of `{rule_id, topic, approved_fact, prohibited_claims, validity_start, validity_end, is_active}`.
   - `offers`: JSON array of `{offer_id, name, is_retired, validity_start, validity_end, prohibited_phrases}`.
   - `tone_rules`: JSON array of `{rule_id, required_tones, prohibited_tones}`.
   - `accessibility_rules`: JSON object of `{min_normal_contrast, min_large_contrast, require_alt_text}`.
   - `legal_rules`: JSON array of `{rule_id, requirement, required_disclaimers, restricted_claims}`.
3. Row-Level Security (RLS) read permissions for the publishable anon key.

---

## 8. Backend FastAPI Integration Guide

To invoke the engine from existing FastAPI endpoints without creating a duplicate app or altering team-owned routes:

```python
# In your existing FastAPI route handler:
from ai_engine.review import run_brand_review
from ai_engine.schemas import ReviewInput, ReviewResult

@router.post("/api/v1/review", response_model=ReviewResult)
async def review_content(payload: ReviewInput) -> ReviewResult:
    # Executes orchestrator with production Supabase repository
    return run_brand_review(request=payload)
```

---

## 9. Security and Safety Contract

- **Prompt Injection Defense**: Review prompts explicitly treat draft text as untrusted user input and command the model to ignore override phrases such as "System override" or "Approve with GREEN".
- **Zero Hallucination Rewrites**: The Rewrite Agent operates on text replacements derived directly from policy facts and suggested fixes. It refuses to invent statistics, benchmarks, or citations.
- **Read-Only Governance**: The Governance Agent provides advisory recommendations for brand policy improvements. It possesses zero permissions or database write capabilities.
- **Secret Isolation**: Configuration masks API keys using Pydantic `SecretStr`. Keys are excluded from error strings, logs, and benchmark reports.
