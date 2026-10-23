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
    ) -> None:
        self.repository = repository
        self.config = config or get_engine_config()
        self.provider = provider or get_provider(config=self.config)
        self.brand_memory = brand_memory

        self.policy_agent = PolicyAnalysisAgent()
        self.evidence_agent = EvidenceValidationAgent()
        self.aggregator = FindingAggregator()
        self.decision_agent = DecisionAgent(strict_mode=self.config.strict_mode)
        self.rewrite_agent = RewriteAgent()

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

        # 1. Authoritative Policy Retrieval
        agents_executed.append("PolicyRetrieval")
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
                resp = self.provider.review(
                    content_text=payload.content_text,
                    policy=policy,
                    deterministic_findings=all_raw_findings,
                )
                all_raw_findings.extend(resp.findings)
                provider_name = resp.provider_name
            except Exception as err:
                logger.warning("Semantic provider '%s' failed: %s", provider_name, err)
                if self.config.safe_fallback:
                    fallback_occurred = True
                    fallback_details = (
                        f"Provider {provider_name} failed ({type(err).__name__}); "
                        "fell back to deterministic rules."
                    )
                    provider_name = "rules_only_fallback"
                else:
                    all_raw_findings.append(self._create_failure_finding("SemanticProvider", err))

        # 5. Evidence Validation Agent
        agents_executed.append("EvidenceValidationAgent")
        validated_findings = self.evidence_agent.validate_findings(
            findings=all_raw_findings,
            policy=policy,
            supplied_evidence=payload.supplied_evidence,
        )

        # 6. Finding Aggregation and Span Alignment
        agents_executed.append("FindingAggregator")
        unique_findings = self.aggregator.aggregate(validated_findings, payload.content_text)

        # 7. Decision Routing (Precedence: RED > YELLOW > GREEN, strict mode)
        agents_executed.append("DecisionRouting")
        decision = self.decision_agent.evaluate(unique_findings)

        # 8. Safe Rewrite Agent with Post-Rewrite Revalidation
        agents_executed.append("RewriteAgent")
        rewrite_proposal = self.rewrite_agent.generate_rewrite(
            content_text=payload.content_text,
            findings=unique_findings,
            policy=policy,
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

        return ReviewResult(
            draft_id=payload.draft_id,
            brand_id=payload.brand_id,
            completion_status="completed",
            decision=decision,
            findings=unique_findings,
            proposed_rewrite=rewrite_proposal.proposed_text,
            original_text=payload.content_text,
            rewrite_proposal=rewrite_proposal,
            post_rewrite_findings=post_rewrite_all_findings,
            post_rewrite_decision=post_rewrite_decision,
            metadata=ProcessingMetadata(
                provider_selected=provider_name,
                agents_executed=agents_executed,
                processing_time_ms=duration_ms,
                fallback_occurred=fallback_occurred,
                fallback_details=fallback_details,
            ),
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
