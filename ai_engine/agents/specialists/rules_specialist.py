"""Rules Specialist Agent.

Deterministic evaluation of brand terminology, product name variants, casing,
and exact spelling rules with character-level span accuracy.
"""

from typing import List
from ai_engine.agents.specialists.base import BaseSpecialist
from ai_engine.rules.terminology import evaluate_terminology
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import Finding
from ai_engine.schemas.payload import DraftPayload


class RulesSpecialist(BaseSpecialist):
    """Specialist responsible for deterministic terminology and spelling rules."""

    @property
    def name(self) -> str:
        return "RulesSpecialist"

    def evaluate(self, payload: DraftPayload, policy: BrandPolicy) -> List[Finding]:
        if not payload.content_text:
            return []

        # Invoke deterministic terminology evaluator
        return evaluate_terminology(payload.content_text, policy)
