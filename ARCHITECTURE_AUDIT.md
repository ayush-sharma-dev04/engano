# ENGANO — Full Multi-Agent Architecture Audit & Alignment Plan

**Date:** 2026-10-23  
**Auditor:** Antigravity AI Engine Pair Programmer  
**Repository:** `Projects/engano` (Branch: `main`)  
**Tools & Skills Used:** Graphify (`/home/ayush/.local/bin/graphify`), Ponytail (`/home/ayush/.gemini/config/plugins/ponytail/skills/ponytail/SKILL.md`), Pytest (`.venv/bin/pytest`)

---

## 1. Executive Summary

An architectural audit of the Engano repository was performed against the complete four-stage multi-agent brand governance specification:
1. **Stage 1 (Adapter Layer):** Multi-channel payload normalization into a canonical `DraftPayload`.
2. **Stage 2 (Coordinator Agent):** Authoritative policy retrieval and concurrent specialist orchestration.
3. **Stage 3 (Specialist Agents & Finding Aggregation):** Dedicated specialists (Rules, Tone, Claims, Visual/WCAG, Legal/Policy), span alignment, evidence validation, and deduplication.
4. **Stage 4 (Decision & Safe Rewrite):** Precedence-based decision routing (`RED > YELLOW > GREEN`), strict mode enforcement, and safe rewrite generation with post-rewrite revalidation.

The codebase currently has strong foundational deterministic rules (`terminology.py`, `claims.py`, `factual.py`, `accessibility.py`), base provider integrations (`gemini.py`, `ollama.py`, `factory.py`), and initial Discord/WhatsApp connectors. However, several critical gaps and workflow misalignments prevent it from functioning as the required end-to-end multi-agent pipeline:
- No canonical `DraftPayload` or unified multi-channel adapter layer exists in `ai_engine` (channels use ad-hoc string passing).
- Specialists are not modeled as modular agents; instead, semantic evaluation is performed as a monolithic prompt call in `ReviewOrchestrator`.
- The Legal & Policy evaluation is missing; Tone and Claims lack isolated specialist agents with grounded policy citations.
- Visual/WCAG checks do not handle logo clear space or explicit missing-metadata states.
- Rewriting does not perform post-rewrite deterministic revalidation and could appear to bypass review requirements.
- Specialist failure handling in `ReviewOrchestrator` can fall back to `rules_only` without escalating or flagging the unverified domain, risking false compliance passes.

---

## 2. Component-by-Component Classification

| Component / Layer | Current Status | Files Affected | Severity | Summary & Required Remediation |
| :--- | :--- | :--- | :--- | :--- |
| **1. Adapter Layer & Canonical Payload** | **PARTIAL / MISALIGNED** | `ai_engine/schemas/review.py`, `ai_engine/adapters/` (new), `Backend/engano_backend/review_service.py`, `Discord/engano_discord/review.py`, `Backend/engano_backend/whatsapp/` | High | Only `ReviewInput` exists (designed for Web Studio text). No canonical `DraftPayload` capturing channel type, images, visual metadata, and channel source metadata. Adapters for Gmail, LinkedIn, and Web Studio are missing; Discord and WhatsApp pass raw strings. **Fix:** Create `DraftPayload` schema and channel adapters (`WebStudioAdapter`, `DiscordAdapter`, `WhatsAppAdapter`, `GmailAdapter`, `LinkedInAdapter`) that normalize to `DraftPayload`. |
| **2. Coordinator Agent (Stage 2)** | **PARTIAL / MISALIGNED** | `ai_engine/agents/orchestrator.py` | High | Orchestrator runs sequentially. Calls a single monolithic LLM prompt instead of dispatching to specialized agents. Lacks concurrent execution for independent specialists. Safe fallback can downgrade provider failures to silent passes. **Fix:** Refactor `ReviewOrchestrator` to act as Coordinator Agent: resolve `BrandLibrary`, execute deterministic rules, execute text specialists (Tone, Claims, Legal) and visual specialist (Visual/WCAG) concurrently via `asyncio`/threading, safely aggregate findings, and fail-closed on critical specialist errors. |
| **3. Rules Specialist Agent** | **IMPLEMENTED** | `ai_engine/rules/terminology.py`, `ai_engine/rules/evaluator.py` | Low | Accurately detects casing, spelling, and prohibited product-name variants (`NimbusDB` vs `Nimbus DB`), produces zero-based character spans, and cites authoritative rules without hallucinating. **Fix:** Wrap cleanly as `RulesSpecialist` conforming to shared specialist contract. |
| **4. Tone Specialist Agent** | **PARTIAL / MISSING** | `ai_engine/prompts/tone_reviewer.md`, `ai_engine/agents/specialists/tone_specialist.py` (new) | Medium | Prompt exists, but no dedicated `ToneSpecialist` exists in runtime code. Tone checking was bundled into generic LLM review. **Fix:** Implement `ToneSpecialist` that evaluates draft against active brand voice/tone rules, returns structured `tone_mismatch` findings with actionable fixes. |
| **5. Claims Specialist Agent** | **PARTIAL** | `ai_engine/rules/claims.py`, `ai_engine/rules/factual.py`, `ai_engine/agents/specialists/claims_specialist.py` (new) | High | Basic pattern matching exists for superlatives, 100% uptime, and retired offers. However, missing benchmark evidence is not clearly separated from proven falsehood in an isolated agent, and semantic claim verification is unintegrated. **Fix:** Implement `ClaimsSpecialist` integrating deterministic factual/claims rules with provider semantic checking, strictly classifying missing evidence as `unsupported` and contradictions as `contradicted`. |
| **6. Visual & WCAG Specialist Agent** | **PARTIAL** | `ai_engine/rules/accessibility.py`, `ai_engine/agents/specialists/visual_wcag_specialist.py` (new) | Medium | WCAG contrast (4.5:1 / 3:1) and alt-text checks exist in `accessibility.py`, but logo clear space and margin rules are not evaluated, and missing metadata is silently skipped rather than reported when required. **Fix:** Implement `VisualWCAGSpecialist` handling contrast, alt-text, logo clear-space, and explicit "not evaluated / unknown" metadata reporting. |
| **7. Legal & Policy Specialist Agent** | **MISSING** | `ai_engine/schemas/brand_policy.py`, `ai_engine/agents/specialists/legal_policy_specialist.py` (new) | High | `BrandPolicy` contains `legal_rules` (required disclaimers, restricted claims), but no evaluator or agent inspects text against them. **Fix:** Implement `LegalPolicySpecialist` to enforce required disclaimers, trademark usage, and restricted claims with grounded rule citations. |
| **8. Finding Aggregation & Span Alignment** | **PARTIAL** | `ai_engine/agents/orchestrator.py`, `ai_engine/rules/evaluator.py`, `ai_engine/agents/aggregator.py` (new) | High | Deduplication in `orchestrator.py` is primitive (tuple of `(category, text)`), discarding distinct violations with overlapping spans, and lacks rigorous revalidation of offsets against the exact draft string. **Fix:** Implement dedicated `FindingAggregator` with span revalidation, subsumption handling, and deterministic deduplication preserving rule provenance and severity. |
| **9. Decision Agent (Stage 4)** | **PARTIAL** | `ai_engine/agents/orchestrator.py`, `ai_engine/agents/decision.py` (new) | High | `_route_decision` implements basic `RED > YELLOW > GREEN`, but strict mode logic in `orchestrator.py` only triggers for medium severity findings, failing to reject non-GREEN drafts as required. Missing formal action enum alignment (`creator_one_click`, `creator_question`, `reviewer_approval`). **Fix:** Formalize `DecisionAgent` enforcing strict precedence and true `strict_mode` rejection. |
| **10. Rewrite Agent** | **PARTIAL / MISALIGNED** | `ai_engine/agents/rewrite.py` | High | `RewriteAgent` performs text replacement but does NOT revalidate the rewritten text against rules and policy checks. It also lacks an explicit guarantee that a rewrite cannot bypass RED approval status. **Fix:** Add post-rewrite revalidation pass running deterministic rules against the rewritten text; enforce that rewrite proposal never alters or overrides an underlying RED decision. |
| **11. Prompt Injection Resistance & Guardrails** | **PARTIAL** | `ai_engine/prompts/`, `ai_engine/providers/` | High | Prompts do not rigorously delineate system policies from untrusted user content using clear boundary delimiters, making them vulnerable to prompt injection attempts that could alter brand decisions. **Fix:** Apply strict boundary encapsulation (`<UNTRUSTED_DRAFT_COPY>`) and add regression tests with malicious prompt injection attacks. |
| **12. Multi-Channel Integration & Compatibility** | **IMPLEMENTED (STANDALONE) / PARTIAL (INTEGRATION)** | `Backend/engano_backend/whatsapp/`, `Discord/engano_discord/` | Medium | WhatsApp and Discord implementations work with text, but bypass `DraftPayload` and cannot pass image metadata or structured attachments to the AI engine. **Fix:** Connect channel handlers through the adapter layer to produce `DraftPayload` without breaking existing user flows or CLI commands. |

---

## 3. Execution Pipeline Alignment Plan

The target runtime pipeline will be structured into four distinct, cohesive stages:

```text
Raw Channel Input (Web Studio, Discord, WhatsApp, Gmail, LinkedIn)
                        |
                        v
        STAGE 1: Adapter Layer (`ai_engine/adapters/`)
        Validate & normalize into canonical `DraftPayload`
                        |
                        v
        STAGE 2: Coordinator Agent (`ai_engine/agents/coordinator.py`)
        Resolve BrandLibrary, select specialists based on payload contents
                        |
                        v
        STAGE 3: Specialist Agents (`ai_engine/agents/specialists/`)
        +-- Rules Specialist (Deterministic: terminology, casing, variants)
        +-- Tone Specialist (Voice, tone mismatch)
        +-- Claims Specialist (Superlatives, SLA facts, retired offers)
        +-- Visual & WCAG Specialist (Contrast, alt-text, logo margins)
        +-- Legal & Policy Specialist (Disclaimers, trademarks, restricted claims)
        (Execute concurrently where safe; fail-closed on critical error)
                        |
                        v
        Finding Aggregation & Span Alignment (`ai_engine/agents/aggregator.py`)
        Deduplication, span revalidation against original draft, evidence classification
                        |
                        v
        STAGE 4: Decision Agent (`ai_engine/agents/decision.py`)
        Precedence evaluation: RED > YELLOW > GREEN; Strict Mode enforcement
                        |
                        +------> Rewrite Agent (`ai_engine/agents/rewrite.py`)
                        |        Generate safe minimal fix + POST-REWRITE REVALIDATION
                        v
        Validated `ReviewResult`
                        |
                        v
        Channel-specific rendering (Discord embeds, WhatsApp text, Web Studio API)
```

---

## 4. Detailed Implementation Tasks

1. **Schemas & Models:**
   - Define canonical `DraftPayload`, `ChannelType`, `ImageItem`, `VisualMetadata` in `ai_engine/schemas/payload.py` (or extend `review.py`).
   - Align action enums: `creator_one_click`, `creator_question`, `reviewer_approval`.
2. **Stage 1 (Adapters):**
   - Implement `ai_engine/adapters/` with adapters for Web Studio, Discord, WhatsApp (supporting image metadata), Gmail, and LinkedIn.
   - Add unit tests for all adapters handling valid, empty, malformed, and image-bearing payloads.
3. **Stage 2 (Coordinator Agent):**
   - Refactor `ai_engine/agents/orchestrator.py` into a robust `CoordinatorAgent` supporting async/concurrent specialist execution and synchronous fallback.
   - Handle provider timeouts and errors fail-closed.
4. **Stage 3 (Specialist Agents & Aggregator):**
   - Implement `RulesSpecialist`, `ToneSpecialist`, `ClaimsSpecialist`, `VisualWCAGSpecialist`, and `LegalPolicySpecialist`.
   - Implement `FindingAggregator` for exact span verification, subsumption, and deduplication.
5. **Stage 4 (Decision & Rewrite):**
   - Implement `DecisionAgent` enforcing `RED > YELLOW > GREEN` and `strict_mode`.
   - Refactor `RewriteAgent` with post-rewrite validation pass.
6. **Integration & Channel Wiring:**
   - Wire `run_brand_review` to accept `DraftPayload` (while maintaining backward compatibility with `ReviewInput`).
   - Update `review_service.py`, Discord adapter, and WhatsApp webhook to leverage the new architecture.
7. **Testing:**
   - Write comprehensive test suite covering all 18 acceptance criteria.
   - Run full pytest test suite and benchmark.
