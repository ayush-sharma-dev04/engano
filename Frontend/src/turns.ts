import type { Finding } from './App'
import type { ReviewSummary, SiteInfo } from './api'
import type { AttachedImage } from './images'

/** The page behind a link the creator put in their message. It is checked alongside the text. */
export type Linked = {
  url: string
  status: 'loading' | 'done' | 'error'
  site?: SiteInfo
  findings?: Finding[]
  summary?: ReviewSummary
  error?: string
}

/** An earlier message and ENGANO's answer, kept above the message being worked on. */
export type Turn = {
  id: number
  title: string
  content: string
  images: AttachedImage[]
  site: SiteInfo | null
  findings: Finding[]
  hidden: Set<number>
  summary: ReviewSummary | null
  error: string | null
  answers: Record<string, string>
  linked: Linked | null
}
