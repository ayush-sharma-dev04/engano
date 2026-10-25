// Client for the ENGANO backend (FastAPI). Base URL comes from VITE_API_URL.
import type { Finding } from './App'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

type ApiFinding = {
  severity: 'low' | 'medium' | 'high' | 'critical'
  category: string
  highlighted_text: string
  text_span?: { start: number; end: number } | null
  explanation: string
  cited_source?: string | null
  suggested_fix?: string | null
  image_index?: number | null
  suggested_alt?: string | null
}

type ApiQuestion = {
  id: string
  kind: 'confirm_brand' | 'website' | 'evidence'
  text: string
  choices?: string[]
  about?: string | null
}

type ApiResult = {
  decision: { status: 'GREEN' | 'YELLOW' | 'RED'; reason?: string | null; clarification_question?: string | null }
  findings: ApiFinding[]
  proposed_rewrite?: string | null
  questions?: ApiQuestion[]
}

export type Question = {
  id: string
  kind: 'confirm_brand' | 'website' | 'evidence'
  text: string
  choices: string[]
  about: string | null
}

export type ReviewSummary = {
  status: 'GREEN' | 'YELLOW' | 'RED'
  reason: string
  question: string | null
  rewrite: string | null
  questions: Question[]
  // Signed proof from the server that exactly this text was reviewed; submissions need it to skip a human.
  receipt: string | null
}

const SEVERITY: Record<ApiFinding['severity'], Finding['severity']> = {
  critical: 'Critical',
  high: 'Critical',
  medium: 'Warning',
  low: 'Suggestion',
}

// Advice, not wording that can be pasted into the draft (mirrors the backend rewrite agent).
const GUIDANCE = /^(rephrase|remove or replace|replace with|check|contact)/i

const CATEGORY: Record<string, string> = {
  terminology: 'Terminology',
  unsupported_claim: 'Unsupported Claim',
  wrong_fact: 'Incorrect Fact',
  outdated_offer: 'Outdated Offer',
  tone_mismatch: 'Tone',
  visual_wcag: 'Accessibility',
  legal: 'Legal',
  brand_guideline: 'Brand Guideline',
}

export async function reviewDraft(
  text: string,
  answers: Record<string, string> = {},
  images: { data: string; alt_text: string }[] = [],
  token: string | null = null
): Promise<{ findings: Finding[]; summary: ReviewSummary }> {
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({
        text,
        ...(Object.keys(answers).length ? { answers } : {}),
        ...(images.length ? { images } : {}),
      }),
    })
  } catch {
    throw new Error(`Could not reach the ENGANO backend at ${API_URL}. Is it running?`)
  }
  if (!response.ok) {
    throw new Error(response.status === 422 ? 'The draft is empty or too long (max 10,000 characters).' : 'The review service is unavailable. Try again shortly.')
  }
  const mapped = mapResult((await response.json()) as ApiResult)
  return { ...mapped, summary: { ...mapped.summary, receipt: response.headers.get('X-Review-Receipt') } }
}

function mapResult(data: ApiResult): { findings: Finding[]; summary: ReviewSummary } {
  const findings: Finding[] = data.findings.map((f) => {
    const fix = f.suggested_fix ?? null
    const append = fix && /^append required disclaimer/i.test(fix) ? fix.match(/'(.+)'\s*$/)?.[1] : undefined
    const literal = fix !== null && !append && !GUIDANCE.test(fix)
    const inImage = f.image_index != null
    const onSite = f.highlighted_text.startsWith('[Website]')
    const hasSpan = !!f.highlighted_text && !append && !inImage && !onSite && f.highlighted_text.length < 400
    const shown = f.highlighted_text.replace(/^\[(Image \d+|Website)\]\s*/, '')
    return {
      severity: SEVERITY[f.severity] ?? 'Warning',
      category: CATEGORY[f.category] ?? f.category,
      issue: onSite ? shown : inImage ? (shown ? `Image ${f.image_index} · “${shown}”` : `Image ${f.image_index}`) : f.highlighted_text ? `“${f.highlighted_text}”` : 'Review could not complete',
      explanation: f.explanation,
      guideline: f.cited_source ?? 'Brand policy',
      suggestion: fix ?? 'Ask a reviewer to check this section.',
      quote: hasSpan ? f.highlighted_text : undefined,
      start: hasSpan ? f.text_span?.start : undefined,
      replacement: hasSpan && literal ? fix : undefined,
      append,
      imageIndex: f.image_index ?? undefined,
      suggestedAlt: f.suggested_alt ?? undefined,
    }
  })

  return {
    findings,
    summary: {
      status: data.decision.status,
      reason: data.decision.reason ?? '',
      question: data.decision.clarification_question ?? null,
      rewrite: data.proposed_rewrite ?? null,
      questions: (data.questions ?? []).map((q) => ({
        id: q.id,
        kind: q.kind,
        text: q.text,
        choices: q.choices ?? [],
        about: q.about ?? null,
      })),
      receipt: null,
    },
  }
}

export type SiteInfo = {
  url: string
  title: string
  screenshot: string
  designNotes: string[]
  designError: string | null
  facts: Record<string, unknown>
}

export async function checkWebsite(url: string): Promise<{ findings: Finding[]; summary: ReviewSummary; site: SiteInfo }> {
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/check-website`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
  } catch {
    throw new Error(`Could not reach the ENGANO backend at ${API_URL}. Is it running?`)
  }
  if (!response.ok) {
    let detail = ''
    try {
      detail = ((await response.json()) as { detail?: unknown }).detail as string
    } catch {
      /* not JSON */
    }
    throw new Error(response.status === 422 && typeof detail === 'string' ? detail : 'Website checks are unavailable. Try again shortly.')
  }
  const data = (await response.json()) as {
    url: string
    title: string
    screenshot: string
    facts: Record<string, unknown>
    design_notes: string[]
    design_error: string | null
    result: ApiResult
  }
  return {
    ...mapResult(data.result),
    site: {
      url: data.url,
      title: data.title,
      screenshot: data.screenshot,
      designNotes: data.design_notes,
      designError: data.design_error,
      facts: data.facts,
    },
  }
}
