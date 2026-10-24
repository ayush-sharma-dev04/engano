"""Schemas for brand governance findings.

Defines finding categories, severity levels, evidence states, text spans,
and validated finding models.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class FindingCategory(str, Enum):
    TERMINOLOGY = "terminology"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    WRONG_FACT = "wrong_fact"
    OUTDATED_OFFER = "outdated_offer"
    TONE_MISMATCH = "tone_mismatch"
    VISUAL_WCAG = "visual_wcag"
    LEGAL = "legal"


class FindingSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceStatus(str, Enum):
    VERIFIED = "verified"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    UNVERIFIED_PROVIDED = "unverified_provided"


class TextSpan(BaseModel):
    """Zero-based, end-exclusive text span [start, end) into the draft text."""
    start: int = Field(ge=0, description="0-based start index (inclusive)")
    end: int = Field(ge=0, description="0-based end index (exclusive)")

    @model_validator(mode="after")
    def validate_indices(self) -> "TextSpan":
        if self.end < self.start:
            raise ValueError(f"Span end ({self.end}) cannot precede start ({self.start})")
        return self


class Finding(BaseModel):
    """Structured brand governance finding."""
    finding_id: str = Field(description="Stable finding identifier")
    category: FindingCategory = Field(description="Category of the finding")
    severity: FindingSeverity = Field(description="Severity of the finding")
    highlighted_text: str = Field(description="Exact snippet highlighted in the draft")
    text_span: TextSpan = Field(description="Exact character span in the submitted draft")
    explanation: str = Field(description="Clear explanation of the violation or issue")
    evidence_status: EvidenceStatus = Field(description="Status of evidence validation")
    cited_source: Optional[str] = Field(default=None, description="Authoritative source citation if applicable")
    suggested_fix: Optional[str] = Field(default=None, description="Proposed replacement or remediation text")
    human_review_required: bool = Field(default=False, description="Flag indicating reviewer approval is required")
    image_index: Optional[int] = Field(default=None, description="1-based number of the attached image this is about")
    suggested_alt: Optional[str] = Field(default=None, description="Suggested alt text for the image, if relevant")

    def validate_against_text(self, full_text: str) -> bool:
        """Validate that text_span matches highlighted_text in full_text."""
        span_slice = full_text[self.text_span.start : self.text_span.end]
        return span_slice == self.highlighted_text
