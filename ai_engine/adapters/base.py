"""Base channel adapter interface.

Defines the contract for transforming raw channel-specific inputs into the canonical
DraftPayload consumed by the Stage 2 Coordinator Agent.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from ai_engine.schemas.payload import DraftPayload


class BaseChannelAdapter(ABC):
    """Abstract base class for all channel ingestion adapters."""

    @abstractmethod
    def normalize(self, raw_input: Any, brand_id: str, draft_id: Optional[str] = None) -> DraftPayload:
        """Normalize raw channel payload into canonical DraftPayload.

        Args:
            raw_input: Raw channel data (dict, dataclass, or model).
            brand_id: Trusted brand identifier (must not be overridden by untrusted payload).
            draft_id: Optional explicit draft identifier.

        Returns:
            Validated DraftPayload.

        Raises:
            ValueError: If input is malformed, missing required fields, or unsupported.
        """
        pass
