"""Email replies: a plain-text part and a simple HTML part."""

from html import escape

from ai_engine.schemas.findings import Finding
from ai_engine.schemas.review import ReviewDecision, ReviewResult

DECISION = {
    ReviewDecision.GREEN: ("🟢", "Ready to publish", "#2e9e5b"),
    ReviewDecision.YELLOW: ("🟡", "Needs your input", "#e0a800"),
    ReviewDecision.RED: ("🔴", "Needs reviewer approval", "#d64545"),
}
INCOMPLETE = ("⚠️", "Review incomplete", "#6b7280")

HELP_TEXT = (
    "ENGANO checks drafts against your brand guidelines and approved facts before you publish.\n\n"
    "Forward a draft email or newsletter to this address, or paste the draft into a new email. "
    "You'll get a reply in this thread with a verdict, each problem with the rule it breaks, "
    "and a suggested fix.\n\n"
    "Nothing is approved or sent anywhere from email."
)
ERROR_TEXT = "Something went wrong while reviewing this draft. Nothing was approved. Please send it again in a moment."
FOOTER = "ENGANO brand review · replies are automatic · approvals happen in the ENGANO studio"


def _label(finding: Finding) -> str:
    return f"{finding.category.value.replace('_', ' ').capitalize()} · {finding.severity.value}"


def render_reply(result: ReviewResult, draft: str, image_count: int = 0) -> tuple[str, str]:
    icon, title, colour = INCOMPLETE if result.completion_status != "completed" else DECISION[result.decision.status]
    rewrite = (
        result.proposed_rewrite
        if result.proposed_rewrite and result.proposed_rewrite.strip() != draft.strip()
        else None
    )

    # Plain text
    lines = [f"{icon} {title}", result.decision.reason]
    if result.decision.clarification_question:
        lines += ["", f"Question: {result.decision.clarification_question}"]
    for i, f in enumerate(result.findings, 1):
        lines += ["", f"{i}. {_label(f)}", f'   "{f.highlighted_text}"' + (f' → "{f.suggested_fix}"' if f.suggested_fix else "")]
        lines.append(f"   {f.explanation}")
        if f.cited_source:
            lines.append(f"   Source: {f.cited_source}")
    if rewrite:
        lines += ["", "Suggested rewrite:", rewrite]
    if image_count:
        lines += ["", "Images were not checked: image checks run in the ENGANO studio."]
    lines += ["", f"Brand: {result.brand_id} · ref {result.draft_id}", "--", FOOTER]
    text = "\n".join(lines)

    # HTML
    parts = [
        f'<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.5;color:#1b2a4a;max-width:640px">',
        f'<div style="border-left:4px solid {colour};padding:8px 12px;margin-bottom:16px">'
        f'<div style="font-size:16px;font-weight:bold">{icon} {escape(title)}</div>'
        f"<div>{escape(result.decision.reason)}</div>",
    ]
    if result.decision.clarification_question:
        parts.append(f"<div style=\"margin-top:8px\"><b>Question:</b> {escape(result.decision.clarification_question)}</div>")
    parts.append("</div>")
    for i, f in enumerate(result.findings, 1):
        change = f'<span style="background:#fde2e2;text-decoration:line-through">{escape(f.highlighted_text)}</span>'
        if f.suggested_fix:
            change += f' → <span style="background:#dcf3e5">{escape(f.suggested_fix)}</span>'
        source = f'<div style="color:#6b7280;font-style:italic">Source: {escape(f.cited_source)}</div>' if f.cited_source else ""
        parts.append(
            f'<div style="margin-bottom:12px"><b>{i}. {escape(_label(f))}</b><br>{change}'
            f"<div>{escape(f.explanation)}</div>{source}</div>"
        )
    if rewrite:
        parts.append(
            '<div style="margin-top:16px"><b>Suggested rewrite</b>'
            f'<div style="background:#f5f3ee;padding:10px 12px;white-space:pre-wrap">{escape(rewrite)}</div></div>'
        )
    if image_count:
        parts.append('<p style="color:#6b7280">Images were not checked: image checks run in the ENGANO studio.</p>')
    parts.append(
        f'<p style="color:#6b7280;font-size:12px;margin-top:24px">Brand: {escape(result.brand_id)} · ref {escape(result.draft_id)}'
        f"<br>{escape(FOOTER)}</p></div>"
    )
    return text, "".join(parts)
