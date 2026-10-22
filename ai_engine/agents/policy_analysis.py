"""Policy Analysis Agent.

Interprets authoritative brand policy provisions relevant to the draft content.
Identifies active rules, terminology constraints, and claim benchmarks without
inventing external rules.
"""

from typing import List, Set
from pydantic import BaseModel, Field
from ai_engine.schemas.brand_policy import BrandPolicy, FactualRule, OfferRule


class PolicyScope(BaseModel):
    """Structured scope of authoritative policy rules applicable to the draft."""
    brand_id: str
    applicable_topics: List[str] = Field(default_factory=list)
    applicable_rule_ids: List[str] = Field(default_factory=list)
    relevant_terms: List[str] = Field(default_factory=list)
    relevant_offers: List[str] = Field(default_factory=list)
    requires_benchmark_verification: bool = False
    requires_uptime_check: bool = False


class PolicyAnalysisAgent:
    """Agent that analyzes draft content against authoritative policy scope."""

    def analyze_scope(self, content_text: str, policy: BrandPolicy) -> PolicyScope:
        """Map draft text to relevant provisions of the authoritative policy."""
        lowered = content_text.lower()
        topics: Set[str] = set()
        rule_ids: Set[str] = set()
        terms: List[str] = []
        offers: List[str] = []

        # 1. Terminology checks
        for term in policy.approved_terminology:
            terms.append(term.approved_term)
            for var in term.prohibited_variants:
                if var.lower() in lowered:
                    topics.add("terminology")
                    rule_ids.add(term.term_id or "term_variant")

        # 2. Performance and benchmark provisions
        requires_benchmark = False
        claims_policy = policy.claims_policy
        for pattern in claims_policy.superlative_patterns:
            if pattern.lower() in lowered:
                topics.add("superlatives")
                rule_ids.add(claims_policy.rule_reference or "claims_superlative")
                requires_benchmark = claims_policy.superlatives_require_benchmark

        # 3. Uptime and SLA provisions
        requires_uptime = False
        for guarantee in claims_policy.forbidden_guarantees:
            if guarantee.lower() in lowered:
                topics.add("guarantees")
                rule_ids.add("claims_guarantee")
                if "uptime" in guarantee.lower():
                    requires_uptime = True

        for fact in policy.factual_rules:
            if fact.topic.lower() in lowered or any(p.lower() in lowered for p in fact.prohibited_claims):
                topics.add(fact.topic)
                rule_ids.add(fact.rule_id)
                if "uptime" in fact.topic.lower():
                    requires_uptime = True

        # 4. Offers
        for offer in policy.offers:
            if offer.name.lower() in lowered or any(p.lower() in lowered for p in offer.prohibited_phrases):
                topics.add("promotional_offers")
                rule_ids.add(offer.offer_id)
                offers.append(offer.name)

        return PolicyScope(
            brand_id=policy.brand_id,
            applicable_topics=sorted(list(topics)),
            applicable_rule_ids=sorted(list(rule_ids)),
            relevant_terms=terms,
            relevant_offers=offers,
            requires_benchmark_verification=requires_benchmark,
            requires_uptime_check=requires_uptime,
        )
