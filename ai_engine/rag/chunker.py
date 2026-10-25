"""Turn a BrandPolicy / BrandMemory into small, self-contained text chunks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ai_engine.schemas.brand_memory import BrandMemory
from ai_engine.schemas.brand_policy import BrandPolicy


class Chunk(BaseModel):
    brand_id: str
    source: str
    source_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _chunk(brand_id: str, source: str, source_id: str, content: str, **meta: Any) -> Chunk:
    return Chunk(brand_id=brand_id, source=source, source_id=source_id, content=content.strip(), metadata=meta)


def chunk_policy(policy: BrandPolicy) -> List[Chunk]:
    """One chunk per rule, so a retrieved chunk can be cited by its id."""
    b = policy.brand_id
    chunks: List[Chunk] = []

    for t in policy.approved_terminology:
        variants = ", ".join(t.prohibited_variants) or "none"
        chunks.append(_chunk(
            b, "terminology", t.term_id,
            f"Approved term: '{t.approved_term}'. Prohibited variants: {variants}.",
            rule_id=t.term_id,
        ))

    cp = policy.claims_policy
    if cp.superlatives_require_benchmark:
        benchmarks = "; ".join(f"{x.benchmark_id}: {x.description}" for x in cp.permitted_benchmarks) or "none"
        chunks.append(_chunk(
            b, "claims", cp.rule_reference or "claims_policy",
            f"Superlatives ({', '.join(cp.superlative_patterns)}) require a permitted benchmark. "
            f"Permitted benchmarks: {benchmarks}. Forbidden guarantees: {', '.join(cp.forbidden_guarantees)}.",
            rule_id=cp.rule_reference,
        ))

    for f in policy.factual_rules:
        if not f.is_active:
            continue
        chunks.append(_chunk(
            b, "fact", f.rule_id,
            f"Approved fact ({f.topic}): {f.approved_fact} "
            f"Prohibited claims: {', '.join(f.prohibited_claims) or 'none'}. "
            f"Valid {f.validity_start} to {f.validity_end}.",
            rule_id=f.rule_id,
        ))

    for o in policy.offers:
        status = "RETIRED, must not be offered" if o.is_retired else "active"
        chunks.append(_chunk(
            b, "offer", o.offer_id,
            f"Offer '{o.name}' ({status}): {o.description}",
            rule_id=o.offer_id,
        ))

    for r in policy.tone_rules:
        chunks.append(_chunk(
            b, "tone", r.rule_id or "tone",
            f"Tone rule: {r.description} Required tones: {', '.join(r.required_tones)}. "
            f"Prohibited tones: {', '.join(r.prohibited_tones)}.",
            rule_id=r.rule_id,
        ))

    for r in policy.legal_rules:
        chunks.append(_chunk(
            b, "legal", r.rule_id,
            f"Legal rule: {r.requirement} Required disclaimers: {'; '.join(r.required_disclaimers)}.",
            rule_id=r.rule_id,
        ))

    return [c for c in chunks if c.content]


def chunk_memory(memory: Optional[BrandMemory]) -> List[Chunk]:
    """Advisory brand context: voice, audience and preferences."""
    if memory is None:
        return []
    b = memory.brand_id
    chunks: List[Chunk] = []
    if memory.description:
        chunks.append(_chunk(b, "memory", "description", f"Brand: {memory.description}"))
    if memory.voice_and_tone_preferences:
        chunks.append(_chunk(b, "memory", "voice", "Preferred voice: " + "; ".join(memory.voice_and_tone_preferences)))
    if memory.target_audience:
        chunks.append(_chunk(b, "memory", "audience", f"Target audience: {memory.target_audience}"))
    for i, fact in enumerate(memory.verified_facts):
        chunks.append(_chunk(b, "memory", f"fact_{i}", f"Brand fact: {fact}"))
    for key, value in memory.custom_preferences.items():
        chunks.append(_chunk(b, "memory", f"pref_{key}", f"Preference '{key}': {value}"))
    return chunks
