"""Persistent Brand Memory Schema.

Defines the structure for durable, cross-session brand context:
- Brand identity and description
- Voice and tone preferences
- Target audience
- Approved terminology
- Verified claims and product facts
- Explicit preferences and constraints
- Reference to authoritative policy

STRICT SEPARATION: Brand memory provides persistent brand context but NEVER
overrides, loosens, or replaces authoritative BrandPolicy rules.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class BrandMemory(BaseModel):
    """Durable, persistent brand context scoped to a specific brand_id."""

    brand_id: str = Field(
        description="Authoritative brand identifier (e.g. 'nimbus_cloud')"
    )
    brand_name: str = Field(
        description="Human-readable brand name (e.g. 'Nimbus Cloud')"
    )
    description: Optional[str] = Field(
        default=None,
        description="Approved brand summary or positioning description"
    )
    voice_and_tone_preferences: List[str] = Field(
        default_factory=list,
        description="Explicit voice and tone preferences (e.g. ['confident', 'technical', 'concise'])"
    )
    target_audience: Optional[str] = Field(
        default=None,
        description="Target customer audience (e.g. 'Enterprise Cloud Architects')"
    )
    approved_terminology: List[str] = Field(
        default_factory=list,
        description="Approved product names and canonical brand terms"
    )
    verified_facts: List[str] = Field(
        default_factory=list,
        description="Verified product facts and substantiated claims"
    )
    custom_preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary explicitly-configured brand preferences and constraints"
    )
    policy_reference: Optional[str] = Field(
        default=None,
        description="Reference or file path to authoritative BrandPolicy"
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of last memory update"
    )
    version: int = Field(
        default=1,
        description="Schema or revision version counter"
    )

    @field_validator("brand_id")
    @classmethod
    def validate_brand_id(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("brand_id must not be empty.")
        if not re.match(r"^[a-z0-9_-]+$", clean):
            raise ValueError(f"brand_id '{v}' contains invalid characters. Use alphanumeric, underscore, or hyphen.")
        return clean
