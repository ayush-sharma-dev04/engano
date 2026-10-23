"""Finding Aggregator and Span Alignment.

Responsible for:
1. Aggregating findings from multiple specialist agents.
2. Deduplicating genuinely equivalent findings while preserving distinct violations.
3. Revalidating zero-based, end-exclusive character spans against original draft text.
4. Preventing unsafe automatic text replacements when offsets are stale or ambiguous.
5. Preserving severity, evidence status, rule provenance, and reviewer context.
"""

from typing import Dict, List, Tuple
from ai_engine.schemas.findings import (
    EvidenceStatus,
    Finding,
    FindingCategory,
    FindingSeverity,
    TextSpan,
)

SEVERITY_WEIGHT = {
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}


class FindingAggregator:
    """Aggregates, aligns, and deduplicates findings from specialist agents."""

    def aggregate(self, findings: List[Finding], original_text: str) -> List[Finding]:
        """Align spans against original text and deduplicate equivalent findings."""
        if not findings:
            return []

        # 1. Span Revalidation and Alignment
        aligned: List[Finding] = []
        for f in findings:
            realigned = self._realign_span(f, original_text)
            aligned.append(realigned)

        # 2. Deduplicate strictly identical or redundant findings
        deduped = self._deduplicate_equivalent(aligned)

        # 3. Resolve subsumption for same-category overlapping findings
        resolved = self._resolve_subsumed(deduped)

        # 4. Deterministic sort: text_span.start ascending, then severity descending
        return sorted(
            resolved,
            key=lambda x: (
                x.text_span.start,
                -SEVERITY_WEIGHT.get(x.severity, 0),
                x.finding_id,
            ),
        )

    def _realign_span(self, finding: Finding, original_text: str) -> Finding:
        """Validate and realign zero-based character offsets against draft text."""
        start = finding.text_span.start
        end = finding.text_span.end
        highlight = finding.highlighted_text

        # Non-text findings (e.g. accessibility, metadata) without highlight keep as is
        if not highlight:
            return finding

        # Check exact slice match if span was positive
        if end > start and original_text[start:end] == highlight:
            return finding

        # Offset mismatch or zero-width span from LLM: search exact substring in original draft
        idx = original_text.find(highlight)
        if idx != -1:
            matched_len = len(highlight)
            return finding.model_copy(update={
                "text_span": TextSpan(start=idx, end=idx + matched_len),
                "highlighted_text": original_text[idx : idx + matched_len],
            })

        # Case-insensitive search fallback
        lowered_text = original_text.lower()
        idx_lower = lowered_text.find(highlight.lower())
        if idx_lower != -1:
            matched_len = len(highlight)
            return finding.model_copy(update={
                "text_span": TextSpan(start=idx_lower, end=idx_lower + matched_len),
                "highlighted_text": original_text[idx_lower : idx_lower + matched_len],
            })

        # Cannot reliably align: clear span and unset suggested_fix to prevent unsafe replacement
        return finding.model_copy(update={
            "text_span": TextSpan(start=0, end=0),
            "suggested_fix": None,
            "human_review_required": True,
        })

    def _deduplicate_equivalent(self, findings: List[Finding]) -> List[Finding]:
        """Deduplicate equivalent findings while preserving distinct policy violations."""
        unique_map: Dict[Tuple[str, int, int, str], Finding] = {}

        for f in findings:
            # Key based on category, span, and normalized text
            key = (
                f.category.value,
                f.text_span.start,
                f.text_span.end,
                f.highlighted_text.strip().lower(),
            )

            if key not in unique_map:
                unique_map[key] = f
            else:
                existing = unique_map[key]
                # Keep the finding with higher severity or verified evidence
                existing_weight = SEVERITY_WEIGHT.get(existing.severity, 0)
                f_weight = SEVERITY_WEIGHT.get(f.severity, 0)

                if f_weight > existing_weight or (
                    f_weight == existing_weight
                    and f.evidence_status == EvidenceStatus.VERIFIED
                    and existing.evidence_status != EvidenceStatus.VERIFIED
                ):
                    unique_map[key] = f

        return list(unique_map.values())

    def _resolve_subsumed(self, findings: List[Finding]) -> List[Finding]:
        """Filter out strictly subsumed text spans within the SAME category.

        Distinct categories (e.g. TERMINOLOGY vs UNSUPPORTED_CLAIM) on overlapping
        spans are PRESERVED.
        """
        # Sort by span length descending
        sorted_by_len = sorted(
            findings,
            key=lambda x: (x.text_span.end - x.text_span.start),
            reverse=True,
        )

        retained: List[Finding] = []
        for candidate in sorted_by_len:
            c_start = candidate.text_span.start
            c_end = candidate.text_span.end

            # Textless findings are always retained
            if c_end <= c_start:
                retained.append(candidate)
                continue

            # Check if strictly subsumed by an already retained finding of the SAME category
            subsumed = False
            for parent in retained:
                if parent.category == candidate.category:
                    p_start = parent.text_span.start
                    p_end = parent.text_span.end
                    if p_start <= c_start and p_end >= c_end and (p_end - p_start) > (c_end - c_start):
                        subsumed = True
                        break

            if not subsumed:
                retained.append(candidate)

        return retained
