import { useRef, useState } from 'react'
import type { Finding } from '../App'
import { checkWebsite, reviewDraft, type ReviewSummary, type SiteInfo } from '../api'
import { Icon } from '../ui'
import StudioChat from '../components/StudioChat'
import { locate } from '../suggestions'
import { problemWith, readImage, type AttachedImage } from '../images'
import { firstLink } from '../links'
import type { Linked, Turn } from '../turns'
import type { DraftOut } from '../useEngano'

type Props = {
  /** Sent with each review so the server can check the draft against this workspace's own rules. */
  token: string
  onSubmit: (draft: DraftOut) => Promise<boolean>
  submitLabel?: string
  // Opens the chat already filled in (an assignment, or a draft to fix and resubmit).
  seed?: { title: string; content: string }
  heading?: string
  subheading?: string
}

/**
 * The review studio: write or paste, ENGANO's agents check it, fix suggestions inline, keep
 * drafting follow-ups. It owns all of that state so a page can mount it once and keep a draft
 * alive while the person looks at other pages.
 */
export default function Studio({
  token,
  onSubmit,
  submitLabel,
  seed,
  heading = 'What are we reviewing today?',
  subheading = 'Paste a post, email or announcement and ENGANO checks it against your brand guidelines.',
}: Props) {
  const [isCreatingDraft, setIsCreatingDraft] = useState(!!seed)
  const [isReviewing, setIsReviewing] = useState(false)

  const [draftTitle, setDraftTitle] = useState(seed?.title ?? '')
  const [content, setContent] = useState(seed?.content ?? '')

  const [findings, setFindings] = useState<Finding[]>([])
  const [history, setHistory] = useState<Turn[]>([])
  const [linked, setLinked] = useState<Linked | null>(null)
  const turnId = useRef(1) // which message is live; lets a slow link check land in the right place
  const [siteMode, setSiteMode] = useState(false)
  const [siteUrl, setSiteUrl] = useState('')
  const [site, setSite] = useState<SiteInfo | null>(null)
  const [images, setImages] = useState<AttachedImage[]>([])
  const [attachError, setAttachError] = useState<string | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [reviewStarted, setReviewStarted] = useState(false)
  const [hidden, setHidden] = useState<Set<number>>(new Set())
  const [reviewSummary, setReviewSummary] = useState<ReviewSummary | null>(null)
  const [reviewError, setReviewError] = useState<string | null>(null)

  const review = async (current: Record<string, string>, text: string = content, attached: AttachedImage[] = images) => {
    setIsReviewing(true)
    setReviewStarted(true)
    setReviewError(null)
    setReviewSummary(null)
    setLinked(null)


    try {
      // The real review: all ENGANO agents run on the backend.
      const { findings: apiFindings, summary } = await reviewDraft(
        text,
        current,
        attached.map((image) => ({ data: image.data, alt_text: image.alt })),
        token
      )
      const newFindings: Finding[] = [...apiFindings]

      if (newFindings.length === 0 && summary.questions.length === 0) {
        newFindings.push({
          severity: 'Suggestion',
          category: 'Brand Check',
          issue: 'No issues detected',
          explanation: 'All ENGANO agents passed this draft against the brand policy.',
          guideline: 'Brand policy',
          suggestion: 'Content can proceed to human review.',
        })
      }

      setHidden(new Set())
      setFindings(newFindings)
      setReviewSummary(summary)
      const link = firstLink(text)
      if (link) startLinked(link)
    } catch (error) {
      setFindings([])
      setReviewError(error instanceof Error ? error.message : 'Review failed.')
    } finally {
      setIsReviewing(false)
    }
  }

  // ==========================================
  // LINKS IN A MESSAGE + FOLLOW-UP MESSAGES
  // ==========================================

  const placeLinked = (turn: number, value: Linked) => {
    if (turnId.current === turn) setLinked(value)
    else setHistory((turns) => turns.map((t) => (t.id === turn ? { ...t, linked: value } : t)))
  }

  // Open the page behind a link in the message. Runs alongside the text review, which shows first.
  const startLinked = (url: string) => {
    const turn = turnId.current
    placeLinked(turn, { url, status: 'loading' })
    checkWebsite(url, token)
      .then((result) => placeLinked(turn, { url, status: 'done', ...result }))
      .catch((error) =>
        placeLinked(turn, { url, status: 'error', error: error instanceof Error ? error.message : 'The link check failed.' })
      )
  }

  // The creator keeps drafting: the message just reviewed moves up, a new one starts below it.
  const sendFollowUp = (text: string) => {
    const message = text.trim()
    if (!message || isReviewing) return
    setHistory((turns) => [
      ...turns,
      {
        id: turnId.current, title: draftTitle, content, images, site, findings, hidden,
        summary: reviewSummary, error: reviewError, answers, linked,
      },
    ])
    turnId.current += 1
    setContent(message)
    setDraftTitle('')
    setImages([])
    setAnswers({})
    setFindings([])
    setHidden(new Set())
    setReviewSummary(null)
    setReviewError(null)
    setSite(null)
    setSiteMode(false)
    setSiteUrl('')
    setLinked(null)
    return review({}, message, [])
  }

  // ==========================================
  // ATTACHED IMAGES
  // ==========================================

  const addImages = async (files: File[]) => {
    setAttachError(null)
    let count = images.length
    const added: AttachedImage[] = []
    for (const file of files) {
      const problem = problemWith(file, count)
      if (problem) {
        setAttachError(problem)
        continue
      }
      try {
        added.push(await readImage(file))
        count += 1
      } catch (error) {
        setAttachError(error instanceof Error ? error.message : 'Could not read that image.')
      }
    }
    if (added.length) setImages((current) => [...current, ...added])
  }

  const removeImage = (id: string) => setImages((current) => current.filter((image) => image.id !== id))

  const setAlt = (id: string, alt: string) =>
    setImages((current) => current.map((image) => (image.id === id ? { ...image, alt } : image)))

  // Open the website in a browser and review what it says and how it looks.
  const checkSite = async () => {
    setIsReviewing(true)
    setReviewStarted(true)
    setReviewError(null)
    setReviewSummary(null)
    try {
      const result = await checkWebsite(siteUrl.trim(), token)
      setHidden(new Set())
      setFindings(result.findings)
      setReviewSummary(result.summary)
      setSite(result.site)
    } catch (error) {
      setFindings([])
      setReviewError(error instanceof Error ? error.message : 'The website check failed.')
    } finally {
      setIsReviewing(false)
    }
  }

  const runReview = () => (site || siteMode ? checkSite() : review(answers))

  // The creator answered ENGANO's questions: keep the answers and check the draft again.
  const answerQuestions = (given: Record<string, string>) => {
    const merged = { ...answers, ...given }
    setAnswers(merged)
    return review(merged)
  }

  // ==========================================
  // INLINE SUGGESTIONS (apply / dismiss)
  // ==========================================

  const hide = (keys: number[]) =>
    setHidden((current) => new Set([...current, ...keys]))

  const applyOne = (text: string, key: number): string => {
    const finding = findings[key]
    if (finding?.append) {
      return text.toLowerCase().includes(finding.append.toLowerCase())
        ? text
        : `${text.trimEnd()} ${finding.append}`
    }
    const spot = locate(text, findings, new Set(
      findings.map((_, i) => i).filter((i) => i !== key)
    ))[0]
    if (!spot || finding?.replacement === undefined) return text
    return text.slice(0, spot.start) + finding.replacement + text.slice(spot.end)
  }

  const applySuggestion = (key: number) => {
    setContent((text) => applyOne(text, key))
    hide([key])
  }

  const applyAllSuggestions = () => {
    // Right-to-left so earlier offsets stay valid.
    const keys = locate(content, findings, hidden)
      .filter((l) => l.finding.replacement !== undefined)
      .sort((a, b) => b.start - a.start)
      .map((l) => l.key)
    const appends = findings
      .map((f, i) => (f.append && !hidden.has(i) ? i : -1))
      .filter((i) => i >= 0)
    let text = content
    for (const key of keys) text = applyOne(text, key)
    for (const key of appends) text = applyOne(text, key)
    setContent(text)
    hide([...keys, ...appends])
  }

  const fixableCount =
    locate(content, findings, hidden).filter((l) => l.finding.replacement !== undefined).length +
    findings.filter((f, i) => f.append && !hidden.has(i)).length

  const resetDraft = () => {
    setIsCreatingDraft(false)
    setDraftTitle('')
    setContent('')
    setFindings([])
    setHidden(new Set())
    setAnswers({})
    setImages([])
    setSite(null)
    setSiteMode(false)
    setSiteUrl('')
    setHistory([])
    setLinked(null)
    turnId.current += 1
    setAttachError(null)
    setReviewStarted(false)
    setReviewSummary(null)
    setReviewError(null)
  }

  const createNewDraft = () => {
    resetDraft()
    setIsCreatingDraft(true)
  }

  const submit = async () => {
    if (content.trim() === '' && !site) return
    const accepted = await onSubmit({
      title: draftTitle,
      content: content.trim() || (site ? `Website check: ${site.url}` : ''),
      findings: findings.filter((_, index) => !hidden.has(index)),
      summary: reviewSummary,
    })
    // Keep the draft if the server refused it, so nothing the creator wrote is lost.
    if (accepted) resetDraft()
  }

  if (!isCreatingDraft) {
    return (
      <div className="rise mx-auto flex min-h-[calc(100vh-9rem)] max-w-2xl flex-col items-center justify-center text-center">
        <h2 className="text-4xl font-semibold tracking-tight">{heading}</h2>

        <p className="mt-3 max-w-md text-sm text-slate-400">{subheading}</p>

        <button onClick={createNewDraft} className="composer mt-10 w-full cursor-text p-5 text-left">
          <p className="text-base text-slate-500">Paste or write your content…</p>

          <div className="mt-10 flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs text-slate-400">
              <span className="rounded-full border border-white/10 px-2.5 py-1">Brand rules</span>
              <span className="rounded-full border border-white/10 px-2.5 py-1">AI agents</span>
            </span>

            <span className="btn-primary px-4 py-2 text-sm">Create draft</span>
          </div>
        </button>

        <p className="mt-5 flex items-center gap-2 text-xs text-slate-500">
          <Icon name="lock" className="h-3.5 w-3.5" />
          Checked against your brand policy. Nothing is published from here.
        </p>
      </div>
    )
  }

  return (
    <StudioChat
      title={draftTitle}
      onTitle={setDraftTitle}
      content={content}
      onContent={setContent}
      findings={findings}
      hidden={hidden}
      onApply={applySuggestion}
      onDismiss={(key) => hide([key])}
      onFixAll={applyAllSuggestions}
      fixableCount={fixableCount}
      started={reviewStarted}
      isReviewing={isReviewing}
      summary={reviewSummary}
      error={reviewError}
      onRun={runReview}
      answers={answers}
      history={history}
      linked={linked}
      onFollowUp={sendFollowUp}
      siteMode={siteMode}
      onSiteMode={setSiteMode}
      siteUrl={siteUrl}
      onSiteUrl={setSiteUrl}
      site={site}
      images={images}
      attachError={attachError}
      onAddImages={addImages}
      onRemoveImage={removeImage}
      onAlt={setAlt}
      onAnswer={answerQuestions}
      onCancel={resetDraft}
      onSubmit={submit}
      submitLabel={submitLabel}
    />
  )
}
