"""Turns Discord content into a review request and renders the result."""

from dataclasses import dataclass, field

import discord
from ai_engine.schemas.findings import Finding
from ai_engine.schemas.review import ReviewDecision, ReviewInput, ReviewResult

MAX_FINDINGS_SHOWN = 6
FIELD_LIMIT = 1024

DECISION_STYLE = {
    ReviewDecision.GREEN: ("🟢 Ready to publish", discord.Colour.from_rgb(46, 158, 91)),
    ReviewDecision.YELLOW: ("🟡 Needs your input", discord.Colour.from_rgb(224, 168, 0)),
    ReviewDecision.RED: ("🔴 Needs reviewer approval", discord.Colour.from_rgb(214, 69, 69)),
}


@dataclass
class Draft:
    """What a Discord user submitted, before it becomes a ReviewInput."""

    channel: str
    author_id: str
    text: str = ""
    image_urls: list[str] = field(default_factory=list)
    source_url: str | None = None

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())

    @property
    def is_empty(self) -> bool:
        return not self.has_text and not self.image_urls

    def to_review_input(self, draft_id: str, brand_id: str) -> ReviewInput:
        return ReviewInput(draft_id=draft_id, brand_id=brand_id, content_text=self.text)


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _code(text: str) -> str:
    # Backticks inside the draft would break Discord's inline code formatting.
    return "`" + text.replace("`", "ˋ") + "`"


def _finding_field(index: int, finding: Finding) -> tuple[str, str]:
    name = f"{index}. {finding.category.value.replace('_', ' ').capitalize()} · {finding.severity.value}"
    change = _code(finding.highlighted_text)
    if finding.suggested_fix:
        change += f" → {_code(finding.suggested_fix)}"
    lines = [change, finding.explanation]
    if finding.cited_source:
        lines.append(f"*Source: {finding.cited_source}*")
    return name, _truncate("\n".join(lines), FIELD_LIMIT)


def render_result(draft: Draft, result: ReviewResult) -> discord.Embed:
    if result.completion_status != "completed":
        title, colour = "⚠️ Review incomplete", discord.Colour.dark_grey()
    else:
        title, colour = DECISION_STYLE[result.decision.status]

    description = result.decision.reason
    if result.decision.clarification_question:
        description += f"\n\n**Question:** {result.decision.clarification_question}"
    embed = discord.Embed(title=title, description=_truncate(description, 4096), colour=colour)

    for i, finding in enumerate(result.findings[:MAX_FINDINGS_SHOWN], 1):
        name, value = _finding_field(i, finding)
        embed.add_field(name=name, value=value, inline=False)
    hidden = len(result.findings) - MAX_FINDINGS_SHOWN
    if hidden > 0:
        embed.add_field(name=f"…and {hidden} more", value="Open the draft in the studio to see all findings.", inline=False)

    if result.proposed_rewrite and result.proposed_rewrite.strip() != draft.text.strip():
        embed.add_field(name="Suggested rewrite", value=_truncate(result.proposed_rewrite, FIELD_LIMIT), inline=False)
    if draft.image_urls:
        embed.add_field(
            name="Images not checked",
            value="Image checks run in the web studio. Only the text was reviewed here.",
            inline=False,
        )

    meta = result.metadata
    embed.set_footer(
        text=f"Brand: {result.brand_id} · {meta.provider_selected} · {meta.processing_time_ms:.0f} ms · {result.draft_id}"
    )
    return embed
