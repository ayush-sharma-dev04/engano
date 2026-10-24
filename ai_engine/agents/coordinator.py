"""Coordinator Agent (Stage 2 of Brand Review Pipeline).

Coordinates end-to-end review lifecycle:
1. Input validation and DraftPayload acceptance
2. Authoritative BrandLibrary retrieval
3. Specialist selection and safe concurrent execution
   - Deterministic RulesSpecialist
   - Text specialists (Tone, Claims, Legal/Policy)
   - Visual & WCAG specialist (when images or visual metadata exist)
4. Safe error handling (fail-closed, never silently convert failures to GREEN)
5. Evidence validation
6. Finding aggregation, deduplication, and span alignment
7. Decision routing (RED > YELLOW > GREEN, strict mode)
8. Minimal safe rewrite generation with post-rewrite revalidation
9. Processing metadata assembly
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
from typing import List, Optional
from ai_engine.agents.aggregator import FindingAggregator
from ai_engine.agents.decision import DecisionAgent, route_decision
from ai_engine.agents.evidence_validation import EvidenceValidationAgent
from ai_engine.agents.policy_analysis import PolicyAnalysisAgent
from ai_engine.agents.rewrite import RewriteAgent
from ai_engine.agents.specialists.base import BaseSpecialist
from ai_engine.agents.specialists.claims_specialist import ClaimsSpecialist
from ai_engine.agents.specialists.legal_policy_specialist import LegalPolicySpecialist
from ai_engine.agents.specialists.rules_specialist import RulesSpecialist
from ai_engine.agents.specialists.tone_specialist import ToneSpecialist
from ai_engine.agents.specialists.visual_wcag_specialist import VisualWCAGSpecialist
from ai_engine.config import EngineConfig, ProviderType, get_engine_config
from ai_engine.integrations.supabase_policy_repository import BasePolicyRepository
from ai_engine.providers.base import BaseProvider
from ai_engine.providers.factory import RulesOnlyProvider, get_provider
from ai_engine.memory.store import get_brand_memory_store
from ai_engine.vision.analyzer import ImageAnalyzer, has_image_data
from ai_engine.vision.specialist import ImageAnalysisSpecialist
from ai_engine.vision.website import WebsiteSpecialist
from ai_engine.agents.questions import (
    BRAND_QUESTION_ID,
    QuestionAgent,
    said_no_to_brand,
    website_notes,
)
from ai_engine.rag.retriever import Retriever, get_retriever
from ai_engine.schemas.brand_memory import BrandMemory
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)
from ai_engine.schemas.payload import DraftPayload
from ai_engine.schemas.review import (
    ActionRequiredBy,
    DecisionOutcome,
    ProcessingMetadata,
    ReviewDecision,
    ReviewResult,
)

logger = logging.getLogger(__name__)


def _route_decision(findings: List[Finding], strict_mode: bool = False) -> DecisionOutcome:
    """Backward compatibility wrapper for decision routing."""
    return route_decision(findings, strict_mode=strict_mode)


class CoordinatorAgent:
    """Stage 2 Coordinator Agent managing specialist dispatch and pipeline execution."""

    def __init__(
        self,
        repository: BasePolicyRepository,
        config: Optional[EngineConfig] = None,
        provider: Optional[BaseProvider] = None,
        brand_memory: Optional[BrandMemory] = None,
        retriever: Optional[Retriever] = None,
    ) -> None:
        self.repository = repository
        self.config = config or get_engine_config()
        self.provider = provider or get_provider(config=self.config)
        self.brand_memory = brand_memory
        self.retriever = retriever if retriever is not None else get_retriever(self.config)

        self.policy_agent = PolicyAnalysisAgent()
        self.evidence_agent = EvidenceValidationAgent()
        self.aggregator = FindingAggregator()
        self.decision_agent = DecisionAgent(strict_mode=self.config.strict_mode)
        self.rewrite_agent = RewriteAgent()
        self.question_agent = QuestionAgent()
        self.image_analyzer = ImageAnalyzer(self.provider)
        self.image_specialist = ImageAnalysisSpecialist()
        self.website_specialist = WebsiteSpecialist()

        # Specialists
        self.rules_specialist = RulesSpecialist()
        self.tone_specialist = ToneSpecialist(provider=self.provider)
        self.claims_specialist = ClaimsSpecialist()
        self.visual_specialist = VisualWCAGSpecialist()
        self.legal_specialist = LegalPolicySpecialist()

    def run_review(self, payload: DraftPayload) -> ReviewResult:
        """Execute the complete bounded 4-stage review pipeline."""
        start_time = time.perf_counter()
        agents_executed: List[str] = ["InputValidation"]
        fallback_occurred = False
        fallback_details = None
        semantic_failure: Optional[Exception] = None

        # 1. Authoritative Policy Retrieval
        agents_executed.append("PolicyRetrieval")
        raw_policy_source = getattr(self.repository, "source_name", None)
        policy_source = (
            raw_policy_source if isinstance(raw_policy_source, str) else type(self.repository).__name__
        )
        logger.info(
            "Reviewing draft '%s' for brand '%s' using policy source '%s'.",
            payload.draft_id,
            payload.brand_id,
            policy_source,
        )
        try:
            policy: Optional[BrandPolicy] = self.repository.get_policy(payload.brand_id)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error("Operational failure retrieving policy from repository: %s", exc)
            return ReviewResult(
                draft_id=payload.draft_id,
                brand_id=payload.brand_id,
                completion_status="operational_failure",
                decision=DecisionOutcome(
                    status=ReviewDecision.RED,
                    action_required_by=ActionRequiredBy.REVIEWER_APPROVAL,
                    clarification_question=None,
                    reason=f"Operational failure: Unable to retrieve authoritative policy ({type(exc).__name__}).",
                ),
                findings=[],
                proposed_rewrite=None,
                metadata=ProcessingMetadata(
                    provider_selected=getattr(self.provider, "provider_name", "unknown"),
                    agents_executed=agents_executed,
                    processing_time_ms=duration_ms,
                    fallback_occurred=False,
                    policy_source=policy_source,
                ),
            )

        if not policy:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ReviewResult(
                draft_id=payload.draft_id,
                brand_id=payload.brand_id,
                completion_status="incomplete_policy",
                decision=DecisionOutcome(
                    status=ReviewDecision.RED,
                    action_required_by=ActionRequiredBy.REVIEWER_APPROVAL,
                    clarification_question=None,
                    reason=f"Authoritative brand policy for '{payload.brand_id}' not found.",
                ),
                findings=[],
                proposed_rewrite=None,
                metadata=ProcessingMetadata(
                    provider_selected=getattr(self.provider, "provider_name", "unknown"),
                    agents_executed=agents_executed,
                    processing_time_ms=duration_ms,
                    fallback_occurred=False,
                    policy_source=policy_source,
                ),
            )

        # 2. Authoritative Policy Scope Analysis & Brand Memory Resolution
        agents_executed.append("PolicyAnalysisAgent")
        self.policy_agent.analyze_scope(payload.content_text, policy)

        # Resolve persistent brand memory context (strictly advisory; never overrides policy rules)
        brand_mem = self.brand_memory
        if brand_mem is None:
            try:
                brand_mem = get_brand_memory_store(config=self.config).get_memory(payload.brand_id)
            except Exception as mem_err:
                logger.info("Brand memory store lookup skipped: %s", mem_err)
        if brand_mem:
            agents_executed.append("BrandMemory")

        # 3. Specialist Execution
        # Rules agent always runs first for every valid draft
        agents_executed.extend(["DeterministicEvaluator", "RulesSpecialist"])
        all_raw_findings: List[Finding] = []
        try:
            rules_findings = self.rules_specialist.evaluate(payload, policy)
            all_raw_findings.extend(rules_findings)
        except Exception as exc:
            logger.error("RulesSpecialist failed: %s", exc)
            all_raw_findings.append(self._create_failure_finding("RulesSpecialist", exc))

        # Look at the images first: the visual checks below read what is measured here.
        has_pictures = any(has_image_data(i) for i in payload.images)
        if has_pictures:
            agents_executed.append("ImageAnalyzer")
            try:
                payload = self.image_analyzer.enrich(payload, policy)
            except Exception as exc:
                logger.error("ImageAnalyzer failed: %s", exc)
                all_raw_findings.append(self._create_failure_finding("ImageAnalyzer", exc))
                has_pictures = False

        # Select secondary specialists based on payload contents
        concurrent_specialists: List[BaseSpecialist] = []

        # Text specialists run when text content exists
        if payload.has_text:
            concurrent_specialists.extend([
                self.tone_specialist,
                self.claims_specialist,
                self.legal_specialist,
            ])

        # Visual specialist runs when images or visual metadata exist
        if payload.has_images_or_visuals:
            concurrent_specialists.append(self.visual_specialist)
        if has_pictures:
            concurrent_specialists.append(self.image_specialist)
        if payload.metadata.get("website_facts"):
            concurrent_specialists.append(self.website_specialist)

        # Run independent specialists concurrently where safe
        if concurrent_specialists:
            with ThreadPoolExecutor(max_workers=min(4, len(concurrent_specialists))) as executor:
                future_to_spec = {
                    executor.submit(spec.evaluate, payload, policy): spec
                    for spec in concurrent_specialists
                }
                for future in as_completed(future_to_spec):
                    spec = future_to_spec[future]
                    agents_executed.append(spec.name)
                    try:
                        spec_findings = future.result()
                        all_raw_findings.extend(spec_findings)
                    except Exception as exc:
                        logger.error("Specialist %s failed: %s", spec.name, exc)
                        all_raw_findings.append(self._create_failure_finding(spec.name, exc))

        # 4. Optional Semantic Provider Analysis (when configured and not rules_only)
        provider_name = getattr(self.provider, "provider_name", "rules_only")
        is_rules_only = (
            provider_name == "rules_only"
            or isinstance(self.provider, RulesOnlyProvider)
            or self.provider.__class__.__name__ == "RulesOnlyProvider"
        )
        if not is_rules_only and payload.has_text:
            agents_executed.append("SemanticProvider")
            try:
                review_kwargs = {}
                context = self._retrieve_context(payload)
                if context:
                    agents_executed.append("RAGRetriever")
                    review_kwargs["context"] = context
                resp = self.provider.review(
                    content_text=payload.content_text,
                    policy=policy,
                    deterministic_findings=all_raw_findings,
                    images=None if has_pictures else payload.images,
                    **review_kwargs,
                )
                all_raw_findings.extend(self._vet_provider_findings(resp.findings, payload.content_text, policy))
                provider_name = resp.provider_name
            except Exception as err:
                semantic_failure = err
                logger.warning("Semantic provider '%s' failed: %s", provider_name, err)
                if self.config.safe_fallback:
                    fallback_occurred = True
                    fallback_details = (
                        f"Provider {provider_name} failed ({type(err).__name__}); "
                        "fell back to deterministic rules."
                    )
                    provider_name = "rules_only_fallback"
                else:
                    logger.info(
                        "Semantic provider failed without safe fallback; continuing with deterministic findings only."
                    )

        # 5. Evidence Validation Agent
        agents_executed.append("EvidenceValidationAgent")
        validated_findings = self.evidence_agent.validate_findings(
            findings=all_raw_findings,
            policy=policy,
            supplied_evidence=payload.supplied_evidence,
        )

        # 6. Finding Aggregation and Span Alignment
        agents_executed.append("FindingAggregator")
        unique_findings = website_notes(
            self.aggregator.aggregate(validated_findings, payload.content_text), payload
        )

        # The creator said this draft is for a different brand: a person must decide.
        if said_no_to_brand(payload.answers):
            unique_findings.append(self._wrong_brand_finding(policy))

        # 6b. Ask for what is missing instead of guessing
        agents_executed.append("QuestionAgent")
        questions = self.question_agent.generate(payload, policy, unique_findings)

        # 7. Decision Routing (Precedence: RED > YELLOW > GREEN, strict mode)
        agents_executed.append("DecisionRouting")
        decision = self.decision_agent.evaluate(unique_findings)
        if questions and decision.status == ReviewDecision.GREEN:
            # Not sure yet: never report "ready to publish" while questions are open.
            decision = DecisionOutcome(
                status=ReviewDecision.YELLOW,
                action_required_by=ActionRequiredBy.CREATOR_QUESTION,
                clarification_question=questions[0].text,
                reason="Review pending: ENGANO needs a little more information.",
            )
        elif questions and not decision.clarification_question:
            decision.clarification_question = questions[0].text

        # 8. Safe Rewrite Agent with Post-Rewrite Revalidation
        agents_executed.append("RewriteAgent")
        rewrite_proposal = self.rewrite_agent.generate_rewrite(
            content_text=payload.content_text,
            findings=unique_findings,
            policy=policy,
            provider=self.provider if not is_rules_only else None,
        )

        # STRICT SAFETY CONTRACT: A rewrite agent must NEVER override a RED decision.
        # A previously blocked draft must not become approved simply because a rewrite was generated.
        if decision.status == ReviewDecision.RED:
            # Overall decision stays strictly RED requiring reviewer approval
            decision.action_required_by = ActionRequiredBy.REVIEWER_APPROVAL
        elif rewrite_proposal.requires_clarification and decision.status == ReviewDecision.YELLOW:
            decision.action_required_by = ActionRequiredBy.CREATOR_QUESTION
            decision.clarification_question = rewrite_proposal.clarification_question

        # Evaluate post-rewrite decision on remaining or new findings
        post_rewrite_all_findings = rewrite_proposal.unresolved_findings + rewrite_proposal.new_findings
        post_rewrite_decision = self.decision_agent.evaluate(post_rewrite_all_findings) if rewrite_proposal.proposed_text else None

        duration_ms = (time.perf_counter() - start_time) * 1000

        if semantic_failure is not None and not self.config.safe_fallback:
            decision.status = ReviewDecision.RED
            decision.action_required_by = ActionRequiredBy.REVIEWER_APPROVAL
            decision.reason = (
                f"Operational failure: Semantic review provider '{provider_name}' failed "
                f"({type(semantic_failure).__name__}). AI review did not complete; "
                "deterministic findings were retained without fabricating a content finding."
            )

        return ReviewResult(
            draft_id=payload.draft_id,
            brand_id=payload.brand_id,
            completion_status="operational_failure" if (semantic_failure is not None and not self.config.safe_fallback) else "completed",
            decision=decision,
            findings=unique_findings,
            proposed_rewrite=rewrite_proposal.proposed_text,
            original_text=payload.content_text,
            rewrite_proposal=rewrite_proposal,
            questions=questions,
            post_rewrite_findings=post_rewrite_all_findings,
            post_rewrite_decision=post_rewrite_decision,
            metadata=ProcessingMetadata(
                provider_selected=provider_name,
                agents_executed=agents_executed,
                processing_time_ms=duration_ms,
                fallback_occurred=fallback_occurred,
                fallback_details=fallback_details,
                policy_source=policy_source,
            ),
        )

    @staticmethod
    def _policy_rule_ids(policy: BrandPolicy) -> List[str]:
        ids = [t.term_id for t in policy.approved_terminology]
        ids += [policy.claims_policy.rule_reference]
        ids += [r.rule_id for r in policy.factual_rules] + [o.offer_id for o in policy.offers]
        ids += [r.rule_id for r in policy.tone_rules] + [r.rule_id for r in policy.legal_rules]
        return [i.lower() for i in ids if i]

    @classmethod
    def _vet_provider_findings(cls, findings: List[Finding], draft: str, policy: BrandPolicy) -> List[Finding]:
        """Keep the LLM advisory. A provider finding survives only if it (1) quotes text that
        is really in the draft and (2) cites a rule that exists in the brand policy. Survivors
        are capped at MEDIUM with human review required, so a model alone can never push a
        draft to RED. The policy rules decide that."""
        norm = " ".join(draft.lower().split())
        known = cls._policy_rule_ids(policy)
        kept: List[Finding] = []
        for f in findings:
            quoted = " ".join(f.highlighted_text.lower().split())
            if quoted and quoted not in norm:
                logger.warning("Dropped ungrounded provider finding (quote not in draft): %.60r", f.highlighted_text)
                continue
            cited = (f.cited_source or "").lower()
            if not any(rule_id in cited for rule_id in known):
                logger.warning("Dropped provider finding citing no policy rule: %.60r (cited %r)", f.highlighted_text, f.cited_source)
                continue
            if f.severity in (FindingSeverity.HIGH, FindingSeverity.CRITICAL):
                f = f.model_copy(update={"severity": FindingSeverity.MEDIUM})
            kept.append(f.model_copy(update={"human_review_required": True}))
        return kept

    def _retrieve_context(self, payload: DraftPayload) -> List[str]:
        """Advisory retrieved context; any failure just means no extra context."""
        if self.retriever is None:
            return []
        try:
            return self.retriever.retrieve(payload.brand_id, payload.content_text)
        except Exception as exc:
            logger.warning("RAG retrieval skipped: %s", exc)
            return []

    @staticmethod
    def _wrong_brand_finding(policy: BrandPolicy) -> Finding:
        return Finding(
            finding_id="wrong_brand",
            category=FindingCategory.LEGAL,
            severity=FindingSeverity.HIGH,
            highlighted_text="",
            text_span=TextSpan(start=0, end=0),
            explanation=(
                f"The creator said this draft is not for {policy.brand_name}, so it cannot be checked "
                "against this brand's policy. A reviewer must decide."
            ),
            evidence_status=EvidenceStatus.UNSUPPORTED,
            cited_source="Brand confirmation",
            suggested_fix=None,
            human_review_required=True,
        )

    def _create_failure_finding(self, specialist_name: str, error: Exception) -> Finding:
        """Create high-severity finding for specialist failure to prevent false compliance passes."""
        return Finding(
            finding_id=f"failure_{specialist_name.lower()}",
            category=FindingCategory.LEGAL if "legal" in specialist_name.lower() else FindingCategory.UNSUPPORTED_CLAIM,
            severity=FindingSeverity.HIGH,
            highlighted_text="",
            text_span=TextSpan(start=0, end=0),
            explanation=(
                f"Specialist '{specialist_name}' failed during review ({type(error).__name__}: {error}). "
                "Operational safety policy requires reviewer approval."
            ),
            evidence_status=EvidenceStatus.UNSUPPORTED,
            cited_source="Safety Policy: Specialist Failure Guardrail",
            suggested_fix=None,
            human_review_required=True,
        )


# Backward-compatible alias
ReviewOrchestrator = CoordinatorAgent
