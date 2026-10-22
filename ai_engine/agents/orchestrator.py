"""Review Orchestrator Agent.

Coordinates end-to-end review lifecycle:
1. Input validation
2. Authoritative policy retrieval
3. Deterministic rule evaluation
4. Provider semantic analysis (Gemini, Ollama, or RulesOnly)
5. Evidence validation
6. Finding deduplication and span verification
7. Decision routing (RED > YELLOW > GREEN, strict mode)
8. Minimal safe rewrite generation
9. Metadata assembly
"""

import logging
import time
from typing import List, Optional
from ai_engine.agents.evidence_validation import EvidenceValidationAgent
from ai_engine.agents.policy_analysis import PolicyAnalysisAgent
from ai_engine.agents.rewrite import RewriteAgent
from ai_engine.config import EngineConfig, ProviderType, get_engine_config
from ai_engine.integrations.supabase_policy_repository import BasePolicyRepository
from ai_engine.providers.base import BaseProvider
from ai_engine.providers.factory import get_provider
from ai_engine.rules.evaluator import evaluate_deterministic_rules
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
)
from ai_engine.schemas.review import (
    ActionRequiredBy,
    DecisionOutcome,
    ProcessingMetadata,
    ReviewDecision,
    ReviewInput,
    ReviewResult,
)

logger = logging.getLogger(__name__)


def _route_decision(findings: List[Finding], strict_mode: bool = False) -> DecisionOutcome:
    """Compute overall decision based on finding severities and evidence states.

    Decision Precedence: RED > YELLOW > GREEN.
    """
    if not findings:
        return DecisionOutcome(
            status=ReviewDecision.GREEN,
            action_required_by=ActionRequiredBy.NONE,
            clarification_question=None,
            reason="All deterministic and semantic brand governance checks passed.",
        )

    has_critical = any(f.severity == FindingSeverity.CRITICAL for f in findings)
    has_contradicted = any(f.evidence_status == EvidenceStatus.CONTRADICTED for f in findings)
    has_high = any(f.severity == FindingSeverity.HIGH for f in findings)

    # 1. RED Condition: Contradictions, retired offers, critical or high severity violations
    if has_critical or has_contradicted or has_high:
        reasons = []
        if has_contradicted:
            reasons.append("contradicts authoritative brand facts or retired offers")
        if has_critical or has_high:
            reasons.append("contains high-risk policy violations or unsupported superlatives")

        return DecisionOutcome(
            status=ReviewDecision.RED,
            action_required_by=ActionRequiredBy.REVIEWER_APPROVAL,
            clarification_question=None,
            reason=f"Review rejected: Draft {', '.join(reasons)}.",
        )

    # 2. YELLOW Condition: Ambiguity, unverified supplied evidence, medium findings
    has_unverified = any(f.evidence_status == EvidenceStatus.UNVERIFIED_PROVIDED for f in findings)
    has_medium = any(f.severity == FindingSeverity.MEDIUM for f in findings)

    if has_unverified or (has_medium and strict_mode):
        question = None
        for f in findings:
            if f.evidence_status == EvidenceStatus.UNVERIFIED_PROVIDED:
                question = f"Can you provide verified source documentation for '{f.highlighted_text}'?"
                break
        if not question and strict_mode:
            question = "Please confirm the highlighted brand corrections before publishing."

        return DecisionOutcome(
            status=ReviewDecision.YELLOW,
            action_required_by=ActionRequiredBy.CREATOR_CLARIFICATION,
            clarification_question=question,
            reason="Review pending: Draft contains unverified evidence or requires author clarification.",
        )

    # 3. GREEN with minor corrections (e.g. terminology with suggested fix)
    has_low_or_fixable_medium = all(
        f.severity in (FindingSeverity.LOW, FindingSeverity.MEDIUM) and f.suggested_fix
        for f in findings
    )

    if has_low_or_fixable_medium and not strict_mode:
        return DecisionOutcome(
            status=ReviewDecision.GREEN,
            action_required_by=ActionRequiredBy.CREATOR_ONE_CLICK_CORRECTION,
            clarification_question=None,
            reason="Approved with recommendations: Apply one-click corrections for terminology or formatting.",
        )

    return DecisionOutcome(
        status=ReviewDecision.YELLOW,
        action_required_by=ActionRequiredBy.CREATOR_ONE_CLICK_CORRECTION,
        clarification_question=None,
        reason="Action required: Correct highlighted findings prior to release.",
    )


class ReviewOrchestrator:
    """Orchestrates end-to-end execution of brand review."""

    def __init__(
        self,
        repository: BasePolicyRepository,
        config: Optional[EngineConfig] = None,
        provider: Optional[BaseProvider] = None,
    ) -> None:
        self.repository = repository
        self.config = config or get_engine_config()
        self.provider = provider or get_provider(config=self.config)
        self.policy_agent = PolicyAnalysisAgent()
        self.evidence_agent = EvidenceValidationAgent()
        self.rewrite_agent = RewriteAgent()

    def run_review(self, request: ReviewInput) -> ReviewResult:
        """Execute complete bounded review pipeline."""
        start_time = time.perf_counter()
        agents_executed: List[str] = ["InputValidation"]
        fallback_occurred = False
        fallback_details = None

        # 1. Authoritative Policy Retrieval
        agents_executed.append("PolicyRetrieval")
        try:
            policy: Optional[BrandPolicy] = self.repository.get_policy(request.brand_id)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error("Operational failure retrieving policy from repository: %s", exc)
            return ReviewResult(
                draft_id=request.draft_id,
                brand_id=request.brand_id,
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
                draft_id=request.draft_id,
                brand_id=request.brand_id,
                completion_status="incomplete_policy",
                decision=DecisionOutcome(
                    status=ReviewDecision.RED,
                    action_required_by=ActionRequiredBy.REVIEWER_APPROVAL,
                    clarification_question=None,
                    reason=f"Authoritative brand policy for '{request.brand_id}' not found.",
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

        # 2. Policy Analysis Agent
        agents_executed.append("PolicyAnalysisAgent")
        scope = self.policy_agent.analyze_scope(request.content_text, policy)

        # 3. Deterministic Rules Evaluation
        agents_executed.append("DeterministicEvaluator")
        deterministic_findings = evaluate_deterministic_rules(
            content_text=request.content_text,
            policy=policy,
            supplied_evidence=request.supplied_evidence,
            visual_metadata=request.visual_metadata,
        )

        # 4. Semantic Review Provider (if not rules_only)
        semantic_findings: List[Finding] = []
        provider_name = getattr(self.provider, "provider_name", "rules_only")

        if self.config.ai_provider != ProviderType.RULES_ONLY:
            agents_executed.append("SemanticProvider")
            try:
                resp = self.provider.review(
                    content_text=request.content_text,
                    policy=policy,
                    deterministic_findings=deterministic_findings,
                )
                semantic_findings = resp.findings
                provider_name = resp.provider_name
            except Exception as err:
                logger.warning("Semantic provider '%s' failed: %s", provider_name, err)
                if self.config.safe_fallback:
                    fallback_occurred = True
                    fallback_details = f"Provider {provider_name} failed ({type(err).__name__}); fell back to deterministic rules."
                    provider_name = "rules_only_fallback"
                else:
                    raise

        # 5. Evidence Validation Agent
        agents_executed.append("EvidenceValidationAgent")
        all_raw_findings = deterministic_findings + semantic_findings
        validated_findings = self.evidence_agent.validate_findings(
            findings=all_raw_findings,
            policy=policy,
            supplied_evidence=request.supplied_evidence,
        )

        # 6. Deduplication and span check
        unique_findings: List[Finding] = []
        normalized_findings: List[Finding] = []

        for f in validated_findings:
            # If span was omitted or zero-width by LLM, attempt to find exact offset in content
            if f.text_span.end <= f.text_span.start and f.highlighted_text:
                idx = request.content_text.lower().find(f.highlighted_text.lower())
                if idx != -1:
                    matched_len = len(f.highlighted_text)
                    f = f.model_copy(update={
                        "text_span": TextSpan(start=idx, end=idx + matched_len),
                        "highlighted_text": request.content_text[idx : idx + matched_len],
                    })
            normalized_findings.append(f)

        # Deduplicate based on span and category/highlight
        dedup_map: dict[tuple[str, str], Finding] = {}
        for f in normalized_findings:
            key = (f.category.value, f.highlighted_text.strip().lower())
            if key not in dedup_map:
                dedup_map[key] = f
            else:
                existing = dedup_map[key]
                # Prefer finding with valid span > 0 or higher severity
                existing_span_len = existing.text_span.end - existing.text_span.start
                f_span_len = f.text_span.end - f.text_span.start
                if f_span_len > existing_span_len:
                    dedup_map[key] = f

        unique_findings = sorted(dedup_map.values(), key=lambda x: x.text_span.start)

        # 7. Decision Routing
        agents_executed.append("DecisionRouting")
        decision = _route_decision(unique_findings, strict_mode=self.config.strict_mode)

        # 8. Safe Rewrite Agent
        agents_executed.append("RewriteAgent")
        rewrite_proposal = self.rewrite_agent.generate_rewrite(
            content_text=request.content_text,
            findings=unique_findings,
            policy=policy,
        )

        # If rewrite requested clarification, reflect in decision if YELLOW
        if rewrite_proposal.requires_clarification and decision.status == ReviewDecision.YELLOW:
            decision.clarification_question = rewrite_proposal.clarification_question

        duration_ms = (time.perf_counter() - start_time) * 1000

        return ReviewResult(
            draft_id=request.draft_id,
            brand_id=request.brand_id,
            completion_status="completed",
            decision=decision,
            findings=unique_findings,
            proposed_rewrite=rewrite_proposal.proposed_text,
            metadata=ProcessingMetadata(
                provider_selected=provider_name,
                agents_executed=agents_executed,
                processing_time_ms=duration_ms,
                fallback_occurred=fallback_occurred,
                fallback_details=fallback_details,
            ),
        )
