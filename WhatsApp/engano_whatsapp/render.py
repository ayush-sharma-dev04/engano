"""WhatsApp reply text. WhatsApp formatting: *bold*, _italic_, ```mono```."""

from ai_engine.schemas.findings import Finding
from ai_engine.schemas.review import ReviewDecision, ReviewResult

from engano_backend.review_service import category_label, rewrite_check_note

MESSAGE_LIMIT = 4096
MAX_FINDINGS_SHOWN = 5

HELP_TEXT = (
    "*ENGANO brand check*\n"
    "Send me the text of a post, email or flyer (or an image with the text as its caption) "
    "before you publish it, and I'll check it "
    "against your brand guidelines and approved facts.\n\n"
    "You'll get a verdict, each problem with the rule it breaks, and a suggested fix. "
    "Nothing is approved or published from WhatsApp."
)
UNSUPPORTED_TEXT = "I can only check text messages and images. Send *help* for how it works."
ERROR_TEXT = "Something went wrong while reviewing this draft. Nothing was approved. Please try again in a moment."

HELP_WORDS = {"help", "hi", "hello", "start", "menu"}

DECISION_HEADLINE = {
    ReviewDecision.GREEN: "🟢 *Ready to publish*",
    ReviewDecision.YELLOW: "🟡 *Needs your input*",
    ReviewDecision.RED: "🔴 *Needs reviewer approval*",
}


def is_help_request(text: str) -> bool:
    return text.strip().lower().strip("!.?") in HELP_WORDS


def _quote(text: str) -> str:
    # Stray formatting characters from the draft would turn into bold/italic.
    return '"' + text.replace("*", "").replace("_", " ").replace("~", "") + '"'


def _finding(index: int, finding: Finding) -> str:
    title = f"*{index}. {category_label(finding.category.value)}* · {finding.severity.value}"
    change = _quote(finding.highlighted_text)
    if finding.suggested_fix:
        change += f" → {_quote(finding.suggested_fix)}"
    lines = [title, change, finding.explanation]
    if finding.cited_source:
        lines.append(f"_Source: {finding.cited_source}_")
    return "\n".join(lines)


def render_result(result: ReviewResult, original_text: str, had_image: bool = False) -> str:
    if result.completion_status != "completed":
        headline = "⚠️ *Review incomplete*"
    else:
        headline = DECISION_HEADLINE[result.decision.status]

    parts = [f"{headline}\n{result.decision.reason}"]
    if result.decision.clarification_question:
        parts.append(f"*Question:* {result.decision.clarification_question}")

    for i, finding in enumerate(result.findings[:MAX_FINDINGS_SHOWN], 1):
        parts.append(_finding(i, finding))
    hidden = len(result.findings) - MAX_FINDINGS_SHOWN
    if hidden > 0:
        parts.append(f"_…and {hidden} more. Open the draft in the studio to see all findings._")

    if result.proposed_rewrite and result.proposed_rewrite.strip() != original_text.strip():
        rewrite = f"*Suggested rewrite*\n{result.proposed_rewrite}"
        if note := rewrite_check_note(result):
            rewrite += f"\n_{note}_"
        parts.append(rewrite)
    if had_image:
        if "ImageAnalyzer" in result.metadata.agents_executed:
            parts.append("_Image: the text in it, its contrast and any logos were checked._")
        else:
            parts.append("_Image: only accessibility was checked. I couldn't open the image itself._")
    parts.append(f"_Brand: {result.brand_id} · ref {result.draft_id}_")

    body = "\n\n".join(parts)
    return body if len(body) <= MESSAGE_LIMIT else body[: MESSAGE_LIMIT - 1] + "…"
