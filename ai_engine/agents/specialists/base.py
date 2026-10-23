"""Base specialist agent contract.

Every specialist inherits from BaseSpecialist and returns schema-validated Finding items.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import Finding
from ai_engine.schemas.payload import DraftPayload


class BaseSpecialist(ABC):
    """Abstract base class for all specialist review agents."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the specialist agent."""
        pass

    @abstractmethod
    def evaluate(self, payload: DraftPayload, policy: BrandPolicy) -> List[Finding]:
        """Evaluate the draft payload against brand policy and return findings."""
        pass
