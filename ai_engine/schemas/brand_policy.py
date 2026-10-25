"""Internal validated representation of Brand Policy models.

Defines the contract consumed by deterministic evaluators and LLM agents.
Does not impose a database schema on Supabase.
"""

from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ApprovedTerm(BaseModel):
    """Configuration for an approved product/brand name and forbidden variants."""
    term_id: Optional[str] = None
    approved_term: str
    prohibited_variants: List[str] = Field(default_factory=list)
    replacement_suggestion: Optional[str] = None
    case_sensitive: bool = False


class PermittedBenchmark(BaseModel):
    """Benchmark reference allowed to support specific performance claims."""
    benchmark_id: str
    description: str


class ClaimsPolicy(BaseModel):
    """Policies governing superlatives, guarantees, and performance claims."""
    superlatives_require_benchmark: bool = True
    rule_reference: Optional[str] = "Rule 4.2"
    superlative_patterns: List[str] = Field(default_factory=list)
    forbidden_guarantees: List[str] = Field(default_factory=list)
    permitted_benchmarks: List[PermittedBenchmark] = Field(default_factory=list)


class FactualRule(BaseModel):
    """Authoritative brand facts, SLAs, and claim validity."""
    rule_id: str
    topic: str
    approved_fact: str
    # Optional brand-configured short replacement wording for claims that
    # contradict `approved_fact`. Falls back to `approved_fact` verbatim when unset.
    suggested_correction: Optional[str] = None
    prohibited_claims: List[str] = Field(default_factory=list)
    validity_start: Optional[date] = None
    validity_end: Optional[date] = None
    is_active: bool = True


class OfferRule(BaseModel):
    """Promotional offers and trial terms with validity periods."""
    offer_id: str
    name: str
    description: Optional[str] = None
    is_retired: bool = False
    validity_start: Optional[date] = None
    validity_end: Optional[date] = None
    prohibited_phrases: List[str] = Field(default_factory=list)


class ToneRule(BaseModel):
    """Tone requirements and prohibited styles."""
    rule_id: str = "Rule 3.1"
    description: Optional[str] = None
    required_tones: List[str] = Field(default_factory=list)
    prohibited_tones: List[str] = Field(default_factory=list)
    # Exact phrases that must not appear (matched case-insensitively on word boundaries).
    prohibited_phrases: List[str] = Field(default_factory=list)


class AccessibilityRules(BaseModel):
    """Deterministic WCAG accessibility thresholds."""
    min_normal_contrast: float = 4.5
    min_large_contrast: float = 3.0
    require_alt_text: bool = True


class LegalRule(BaseModel):
    """Configured legal and regulatory requirements."""
    rule_id: str
    requirement: str
    required_disclaimers: List[str] = Field(default_factory=list)
    restricted_claims: List[str] = Field(default_factory=list)
    # Phrases that make `required_disclaimers` mandatory (e.g. "SLA", "uptime").
    # When empty, the legacy absolute-SLA patterns are used.
    trigger_phrases: List[str] = Field(default_factory=list)


class LogoRules(BaseModel):
    """What the brand expects to see (and not see) in images."""
    require_brand_logo: bool = False
    # Other companies whose logos may appear (partners, sponsors). Any other mark is flagged.
    approved_partners: List[str] = Field(default_factory=list)


class VisualStyle(BaseModel):
    """The brand's look: fonts and colours a website or design should stay within."""
    fonts: List[str] = Field(default_factory=list)
    # Hex colours such as "#1E3CC8".
    colors: List[str] = Field(default_factory=list)


class BrandPolicy(BaseModel):
    """Authoritative brand policy loaded into the review engine."""
    brand_id: str
    brand_name: str
    description: Optional[str] = None
    approved_terminology: List[ApprovedTerm] = Field(default_factory=list)
    claims_policy: ClaimsPolicy = Field(default_factory=ClaimsPolicy)
    factual_rules: List[FactualRule] = Field(default_factory=list)
    offers: List[OfferRule] = Field(default_factory=list)
    tone_rules: List[ToneRule] = Field(default_factory=list)
    accessibility_rules: AccessibilityRules = Field(default_factory=AccessibilityRules)
    legal_rules: List[LegalRule] = Field(default_factory=list)
    logo_rules: LogoRules = Field(default_factory=LogoRules)
    visual_style: VisualStyle = Field(default_factory=VisualStyle)
    test_fixtures: Optional[Dict[str, Any]] = None
