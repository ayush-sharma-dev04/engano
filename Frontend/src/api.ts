// Client for the ENGANO backend (FastAPI). Base URL comes from VITE_API_URL.
import type { Finding } from './App'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

type ApiFinding = {
  severity: 'low' | 'medium' | 'high' | 'critical'
  category: string
  highlighted_text: string
  explanation: string
  cited_source?: string | null
  suggested_fix?: string | null
}

type ApiResult = {
  decision: { status: 'GREEN' | 'YELLOW' | 'RED'; reason?: string | null; clarification_question?: string | null }
  findings: ApiFinding[]
  proposed_rewrite?: string | null
}

export type ReviewSummary = {
  status: 'GREEN' | 'YELLOW' | 'RED'
  reason: string
  question: string | null
  rewrite: string | null
}

const SEVERITY: Record<ApiFinding['severity'], Finding['severity']> = {
  critical: 'Critical',
  high: 'Critical',
  medium: 'Warning',
  low: 'Suggestion',
}

const CATEGORY: Record<string, string> = {
  terminology: 'Terminology',
  unsupported_claim: 'Unsupported Claim',
  wrong_fact: 'Incorrect Fact',
  outdated_offer: 'Outdated Offer',
  tone_mismatch: 'Tone',
  visual_wcag: 'Accessibility',
  legal: 'Legal',
}

export async function reviewDraft(text: string): Promise<{ findings: Finding[]; summary: ReviewSummary }> {
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
  } catch {
    throw new Error(`Could not reach the ENGANO backend at ${API_URL}. Is it running?`)
  }
  if (!response.ok) {
    throw new Error(response.status === 422 ? 'The draft is empty or too long (max 10,000 characters).' : 'The review service is unavailable. Try again shortly.')
  }
  const data = (await response.json()) as ApiResult

  const findings: Finding[] = data.findings.map((f) => ({
    severity: SEVERITY[f.severity] ?? 'Warning',
    category: CATEGORY[f.category] ?? f.category,
    issue: f.highlighted_text ? `“${f.highlighted_text}”` : 'Review could not complete',
    explanation: f.explanation,
    guideline: f.cited_source ?? 'Brand policy',
    suggestion: f.suggested_fix ?? 'Ask a reviewer to check this section.',
  }))

  return {
    findings,
    summary: {
      status: data.decision.status,
      reason: data.decision.reason ?? '',
      question: data.decision.clarification_question ?? null,
      rewrite: data.proposed_rewrite ?? null,
    },
  }
}
