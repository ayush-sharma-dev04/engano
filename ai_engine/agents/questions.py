"""Question Agent.

Decides when ENGANO should ask the creator for more information instead of guessing.
Rule-based on purpose: every question points at a concrete gap (a claim with no proof,
a draft that never mentions the brand), never at a model's hunch.

Questions ENGANO can ask:
  confirm_brand  The draft never mentions the brand it is being checked against.
  website        There are claims to back up and no company website to read yet.
  evidence       A specific claim has no benchmark or source.
"""

from __future__ import annotations

import hashlib
import re
from typing import List

from ai_engine.schemas.brand_policy import BrandPolicy
from ai_engine.schemas.findings import EvidenceStatus, Finding, FindingCategory
from ai_engine.schemas.payload import DraftPayload
from ai_engine.schemas.review import ClarifyingQuestion

IMAGE_TAG = re.compile(r"^\[Image \d+\]\s*")
MIN_WORDS_FOR_BRAND_CHECK = 40
MAX_EVIDENCE_QUESTIONS = 3
BRAND_QUESTION_ID = "brand"
WEBSITE_QUESTION_ID = "website"


def evidence_question_id(highlighted_text: str) -> str:
    digest = hashlib.sha1(highlighted_text.strip().lower().encode()).hexdigest()[:8]
    return f"evidence:{digest}"


def brand_names(policy: BrandPolicy) -> List[str]:
    """Every name the brand goes by: brand name, approved terms, and known variants."""
    names = [policy.brand_name]
    for term in policy.approved_terminology:
        names.append(term.approved_term)
        names.extend(term.prohibited_variants)
    return [n.strip().lower() for n in names if n and n.strip()]


def mentions_brand(text: str, policy: BrandPolicy) -> bool:
    lowered = text.lower()
    return any(re.search(rf"(?<!\w){re.escape(name)}(?!\w)", lowered) for name in brand_names(policy))


def said_no_to_brand(answers: dict) -> bool:
    return answers.get(BRAND_QUESTION_ID, "").strip().lower().startswith("no")


class QuestionAgent:
    def generate(self, payload: DraftPayload, policy: BrandPolicy, findings: List[Finding]) -> List[ClarifyingQuestion]:
        answers = payload.answers or {}
        questions: List[ClarifyingQuestion] = []

        # 1. Is this draft even about this brand?
        if (
            BRAND_QUESTION_ID not in answers
            and len(payload.content_text.split()) >= MIN_WORDS_FOR_BRAND_CHECK
            and not mentions_brand(payload.content_text, policy)
        ):
            questions.append(
                ClarifyingQuestion(
                    id=BRAND_QUESTION_ID,
                    kind="confirm_brand",
                    text=(
                        f"I can't find {policy.brand_name} or any of its product names in this draft. "
                        f"Is it written for {policy.brand_name}?"
                    ),
                    choices=[f"Yes, it's for {policy.brand_name}", "No, it's for another brand"],
                )
            )

        # 2. Claims with no proof
        needs_proof = [
            f for f in findings
            if f.category == FindingCategory.UNSUPPORTED_CLAIM
            and f.evidence_status == EvidenceStatus.UNSUPPORTED
            and f.highlighted_text.strip()
        ]
        # One question per distinct claim: a shorter phrase inside a longer one is the same claim.
        phrases: List[str] = []
        for f in needs_proof:
            phrase = IMAGE_TAG.sub("", f.highlighted_text).strip()
            lowered = phrase.lower()
            if any(lowered in p.lower() for p in phrases):
                continue
            phrases = [p for p in phrases if p.lower() not in lowered] + [phrase]
        for phrase in phrases[:MAX_EVIDENCE_QUESTIONS]:
            key = evidence_question_id(phrase)
            if key in answers:
                continue
            questions.append(
                ClarifyingQuestion(
                    id=key,
                    kind="evidence",
                    text=(
                        f"Do you have a benchmark, report or page that backs up “{phrase}”? "
                        "Paste its name (for example a benchmark ID) or a link."
                    ),
                    about=phrase,
                )
            )

        # 3. A company website helps when there are claims to check
        first_ask = WEBSITE_QUESTION_ID not in answers and bool(needs_proof)
        retry = bool(payload.website_error) and WEBSITE_QUESTION_ID in answers
        if first_ask or retry:
            reason = (
                f"I couldn't open that address ({payload.website_error}). Could you check the link?"
                if payload.website_error
                else "What is your company website? I'll read it to see whether it supports these claims."
            )
            questions.append(ClarifyingQuestion(id=WEBSITE_QUESTION_ID, kind="website", text=reason))

        return questions


def website_notes(findings: List[Finding], payload: DraftPayload) -> List[Finding]:
    """Tell the reviewer when a flagged claim also appears on the company's own site.

    The site is the creator's own material, so this never clears a finding; it only
    adds context to the explanation.
    """
    if not payload.website_text:
        return findings
    site = " ".join(payload.website_text.lower().split())
    where = payload.website_url or "the company website"
    noted: List[Finding] = []
    for f in findings:
        phrase = " ".join(f.highlighted_text.lower().split())
        if f.category == FindingCategory.UNSUPPORTED_CLAIM and phrase and phrase in site:
            f = f.model_copy(update={
                "explanation": f"{f.explanation} The same claim appears on {where}, but that is the company's own "
                               "page and does not count as independent evidence.",
            })
        noted.append(f)
    return noted
