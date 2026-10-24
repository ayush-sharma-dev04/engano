"""When ENGANO is not sure, a person decides.

A review is escalated to the human reviewer when the engine could not settle it by
itself: the review did not complete, the decision needs reviewer approval (RED), or a
finding is marked for human review. Clean (GREEN) results with nothing to double-check
are never escalated.

The reviewer is configured in the root .env:
    ENGANO_REVIEWER_WHATSAPP=919876500001      # country code + number
    ENGANO_REVIEWER_DISCORD_ID=100000000000000001
    ENGANO_DEFAULT_COUNTRY_CODE=91             # prepended to 10-digit numbers
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ai_engine.schemas.review import ActionRequiredBy, ReviewDecision, ReviewResult

from .review_service import category_label

MAX_DRAFT_CHARS = 1200
MAX_FINDINGS = 6


def normalize_whatsapp_number(raw: str | None, default_country_code: str = "91") -> str | None:
    """Digits only, in WhatsApp's wa_id form (country code + number, no '+')."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    if len(digits) == 10:  # national number without a country code
        digits = default_country_code + digits
    return digits


@dataclass(frozen=True)
class EscalationSettings:
    whatsapp_number: str | None = None
    discord_user_id: int | None = None

    @classmethod
    def from_env(cls) -> "EscalationSettings":
        raw_discord = re.sub(r"\D", "", os.getenv("ENGANO_REVIEWER_DISCORD_ID", ""))
        return cls(
            whatsapp_number=normalize_whatsapp_number(
                os.getenv("ENGANO_REVIEWER_WHATSAPP"),
                re.sub(r"\D", "", os.getenv("ENGANO_DEFAULT_COUNTRY_CODE", "")) or "91",
            ),
            discord_user_id=int(raw_discord) if raw_discord else None,
        )


def escalation_reasons(result: ReviewResult) -> List[str]:
    """Why a person should look at this. Empty list means no escalation."""
    reasons: List[str] = []
    if result.completion_status != "completed":
        reasons.append(f"The review did not complete ({result.completion_status}).")
    if result.decision.status == ReviewDecision.RED or (
        result.decision.action_required_by == ActionRequiredBy.REVIEWER_APPROVAL
    ):
        reasons.append("The decision requires reviewer approval.")
    if any(f.human_review_required for f in result.findings):
        reasons.append("At least one finding is marked for human review (the engine is not sure).")
    return reasons


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def reviewer_message(
    result: ReviewResult,
    draft_text: str,
    channel: str,
    sender: str,
    reasons: List[str],
    source_url: Optional[str] = None,
) -> str:
    """Plain-text hand-off for the reviewer (readable in WhatsApp and Discord)."""
    status = result.decision.status.value if result.completion_status == "completed" else "INCOMPLETE"
    lines = [
        "ENGANO: a draft needs your review",
        f"Channel: {channel}  |  From: {sender}  |  Brand: {result.brand_id}",
        f"Engine verdict: {status}",
        *[f"- {r}" for r in reasons],
        "",
        "Draft:",
        _clip(draft_text.strip() or "(no text, image only)", MAX_DRAFT_CHARS),
        "",
        "Findings:" if result.findings else "Findings: none recorded",
    ]
    for i, f in enumerate(result.findings[:MAX_FINDINGS], 1):
        flag = " [needs human check]" if f.human_review_required else ""
        line = f'{i}. {category_label(f.category.value)} ({f.severity.value}){flag}: "{_clip(f.highlighted_text, 120)}"'
        if f.suggested_fix:
            line += f' -> "{_clip(f.suggested_fix, 120)}"'
        lines.append(line)
        lines.append(f"   {_clip(f.explanation, 300)}" + (f" [{f.cited_source}]" if f.cited_source else ""))
    if len(result.findings) > MAX_FINDINGS:
        lines.append(f"...and {len(result.findings) - MAX_FINDINGS} more")
    if result.proposed_rewrite and result.proposed_rewrite.strip() != draft_text.strip():
        lines += ["", "Suggested rewrite (not approved):", _clip(result.proposed_rewrite, MAX_DRAFT_CHARS)]
    if source_url:
        lines.append(f"\nSource: {source_url}")
    lines.append(f"\nRef: {result.draft_id}")
    return "\n".join(lines)


def escalation_for(result: ReviewResult) -> Tuple[bool, List[str]]:
    reasons = escalation_reasons(result)
    return bool(reasons), reasons
