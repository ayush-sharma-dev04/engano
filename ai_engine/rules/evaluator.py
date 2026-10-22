"""Deterministic evaluation pipeline.

Coordinates all deterministic rule checks (terminology, claims, factual,
accessibility), deduplicates findings, and validates text spans.
"""

from typing import Any, List, Optional
from ai_engine.rules.accessibility import evaluate_accessibility
from ai_engine.rules.claims import evaluate_claims
from ai_engine.rules.factual import evaluate_factual
from ai_engine.rules.terminology import evaluate_terminology
from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import Finding, FindingSeverity
from ai_engine.schemas.review import VisualMetadata


SEVERITY_ORDER = {
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}


def _deduplicate_findings(findings: List[Finding]) -> List[Finding]:
    """Deduplicate findings, preferring higher severity and larger subsuming spans."""
    # 1. Deduplicate exact spans first by keeping highest severity
    exact_map: dict[tuple[int, int], Finding] = {}
    for f in findings:
        span_key = (f.text_span.start, f.text_span.end)
        if span_key not in exact_map:
            exact_map[span_key] = f
        else:
            existing = exact_map[span_key]
            if SEVERITY_ORDER.get(f.severity, 0) > SEVERITY_ORDER.get(existing.severity, 0):
                exact_map[span_key] = f

    # 2. Filter out strictly subsumed spans of same category (e.g. 'fastest database' inside 'fastest database in the world')
    sorted_findings = sorted(
        exact_map.values(),
        key=lambda x: (x.text_span.end - x.text_span.start),
        reverse=True,
    )

    final_findings: List[Finding] = []
    for candidate in sorted_findings:
        # Check if candidate is a sub-span of an already accepted finding with same category
        c_start = candidate.text_span.start
        c_end = candidate.text_span.end
        if c_end > c_start:  # Only for text-based spans
            is_subsumed = any(
                accepted.text_span.start <= c_start
                and c_end <= accepted.text_span.end
                and (accepted.text_span.end - accepted.text_span.start) > (c_end - c_start)
                and accepted.category == candidate.category
                for accepted in final_findings
            )
            if is_subsumed:
                continue
        final_findings.append(candidate)

    # Sort final findings in reading order by start index
    return sorted(final_findings, key=lambda x: x.text_span.start)


def evaluate_deterministic_rules(
    content_text: str,
    policy: BrandPolicy,
    supplied_evidence: Optional[Any] = None,
    visual_metadata: Optional[VisualMetadata] = None,
) -> List[Finding]:
    """Execute all configured deterministic evaluators and return validated, deduplicated findings."""
    raw_findings: List[Finding] = []

    # 1. Terminology checks
    raw_findings.extend(evaluate_terminology(content_text, policy))

    # 2. Claims checks
    raw_findings.extend(evaluate_claims(content_text, policy, supplied_evidence))

    # 3. Factual and offer validity checks
    raw_findings.extend(evaluate_factual(content_text, policy))

    # 4. Accessibility checks (only if metadata provided)
    raw_findings.extend(evaluate_accessibility(visual_metadata, policy))

    # 5. Span validation and deduplication
    valid_findings: List[Finding] = []
    for f in raw_findings:
        # Validate span bounds if text_span covers text
        if f.text_span.end > f.text_span.start:
            if not f.validate_against_text(content_text):
                # Fallback safeguard: if span mismatch, log and omit to protect span integrity
                continue
        valid_findings.append(f)

    return _deduplicate_findings(valid_findings)
