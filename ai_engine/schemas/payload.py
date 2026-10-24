"""Canonical DraftPayload schemas for multi-channel intake.

Defines the normalized data model produced by Stage 1 channel adapters
and consumed by Stage 2 Coordinator Agent.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    """Supported ingestion channels."""
    WEB_STUDIO = "web_studio"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    GMAIL = "gmail"
    LINKEDIN = "linkedin"


class ImageItem(BaseModel):
    """Normalized image or visual asset attached to a draft."""
    url: Optional[str] = Field(default=None, description="Image URL or local reference")
    alt_text: Optional[str] = Field(default=None, description="Alternative text description")
    contrast_ratio: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=21.0,
        description="Measured text-to-background contrast ratio",
    )
    is_large_text: bool = Field(default=False, description="True if text is >= 18pt or 14pt bold")
    logo_clear_space_met: Optional[bool] = Field(
        default=None,
        description="True if required brand logo margin is maintained",
    )
    mime_type: Optional[str] = Field(default=None, description="MIME type (e.g. image/png)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional image metadata")


class VisualMetadata(BaseModel):
    """Visual and accessibility measurements for copy and imagery."""
    contrast_ratio: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=21.0,
        description="Measured contrast ratio against background",
    )
    is_large_text: bool = Field(default=False, description="True if text size is >= 18pt or 14pt bold")
    has_alt_text: Optional[bool] = Field(default=None, description="True if alternative text is provided")
    logo_clear_space_met: Optional[bool] = Field(default=None, description="True if logo margins are met")


class DraftPayload(BaseModel):
    """Canonical normalized payload ingested across all supported channels."""
    draft_id: str = Field(description="Unique draft or message identifier")
    brand_id: str = Field(description="Authoritative brand identifier to evaluate against")
    channel: ChannelType = Field(default=ChannelType.WEB_STUDIO, description="Originating channel")
    content_text: str = Field(default="", description="Draft copy or text content")
    images: List[ImageItem] = Field(default_factory=list, description="Visual assets attached to draft")
    visual_metadata: Optional[VisualMetadata] = Field(
        default=None,
        description="Explicit visual/accessibility measurements",
    )
    supplied_evidence: Optional[Any] = Field(
        default=None,
        description="Optional evidence (benchmarks, whitepapers) supplied by creator",
    )
    answers: Dict[str, str] = Field(
        default_factory=dict,
        description="Creator's answers to earlier clarifying questions (question id -> answer)",
    )
    website_url: Optional[str] = Field(default=None, description="Company website the creator gave (already fetched)")
    website_text: Optional[str] = Field(default=None, description="Readable text fetched from website_url")
    website_error: Optional[str] = Field(default=None, description="Why the website could not be read, if so")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Preserved source channel metadata (untrusted, cannot override trusted config)",
    )

    @property
    def has_text(self) -> bool:
        """Return True if non-empty text content is present."""
        return bool(self.content_text and self.content_text.strip())

    @property
    def has_images_or_visuals(self) -> bool:
        """Return True if images or explicit visual measurements are present."""
        return bool(self.images or self.visual_metadata is not None)
