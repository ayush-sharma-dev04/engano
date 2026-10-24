import { useRef, useState } from 'react'
import { checkWebsite, reviewDraft, type ReviewSummary, type SiteInfo } from './api'
import { Icon } from './ui'
import StudioChat from './components/StudioChat'
import { locate } from './suggestions'
import { problemWith, readImage, type AttachedImage } from './images'
import { firstLink } from './links'
import type { Linked, Turn } from './turns'
import BrandGuidelines from './components/BrandGuidelines'
import ReviewQueue, {
  type ReviewSubmission,
} from './components/ReviewQueue'
import Approvals from './components/Approvals'
import History from './components/History'
import Insights from './components/Insights'

export type Finding = {
  severity: 'Critical' | 'Warning' | 'Suggestion'
  category: string
  issue: string
  explanation: string
  guideline: string
  suggestion: string
  // Set for findings that can be underlined and fixed inside the editor.
  quote?: string
  start?: number
  replacement?: string
  append?: string
  // Set when the finding is about an attached image (1-based).
  imageIndex?: number
  suggestedAlt?: string
}

export type Guideline = {
  id: number
  type: 'DO' | "DON'T"
  text: string
}

function App() {
  const [activePage, setActivePage] = useState('studio')
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const [isCreatingDraft, setIsCreatingDraft] = useState(false)
  const [isReviewing, setIsReviewing] = useState(false)

  const [draftTitle, setDraftTitle] = useState('')
  const [content, setContent] = useState('')

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

  // ==========================================
  // SHARED BRAND LIBRARY
  // ==========================================

  const [guidelines, setGuidelines] = useState<Guideline[]>([])

  // ==========================================
  // REVIEW QUEUE
  // ==========================================

  const [submissions, setSubmissions] = useState<ReviewSubmission[]>([])

  // Currently opened submission
  const [selectedSubmission, setSelectedSubmission] =
    useState<ReviewSubmission | null>(null)
  const [changeRequestComment, setChangeRequestComment] = useState('')
  const [showChangeRequestModal, setShowChangeRequestModal] = useState(false)

  // ==========================================
  // RUN ENGANO REVIEW
  // ==========================================

  const review = async (current: Record<string, string>, text: string = content, attached: AttachedImage[] = images) => {
    setIsReviewing(true)
    setReviewStarted(true)
    setReviewError(null)
    setReviewSummary(null)
    setLinked(null)

    const lowerContent = text.toLowerCase()

    try {
      // The real review: all ENGANO agents run on the backend.
      const { findings: apiFindings, summary } = await reviewDraft(
        text,
        current,
        attached.map((image) => ({ data: image.data, alt_text: image.alt }))
      )
      const newFindings: Finding[] = [...apiFindings]

      // Custom DO / DON'T rules from the Brand Library are still checked in the browser.
    guidelines.forEach((guideline) => {
      const guidelineWords = guideline.text
        .toLowerCase()
        .replace(/[.,!?'"()]/g, '')
        .split(/\s+/)
        .filter((word) => word.length > 3)

      if (guideline.type === "DON'T") {
        const matchedWord = guidelineWords.find((word) =>
          lowerContent.includes(word)
        )

        if (matchedWord) {
          const alreadyDetected = newFindings.some(
            (finding) =>
              finding.guideline.toLowerCase() ===
              guideline.text.toLowerCase()
          )

          if (!alreadyDetected) {
            newFindings.push({
              severity: 'Warning',
              category: 'Brand Guideline',
              issue: 'Brand guideline may be violated',
              explanation:
                `The content contains "${matchedWord}", which may conflict with a rule configured in the Brand Library.`,
              guideline: guideline.text,
              suggestion:
                'Review this statement and rewrite it to comply with the configured brand guideline.',
            })
          }
        }
      }
    })

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
    checkWebsite(url)
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
      const result = await checkWebsite(siteUrl.trim())
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

  // ==========================================
  // CREATE NEW DRAFT
  // ==========================================

  const createNewDraft = () => {
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
    setIsCreatingDraft(true)
  }

  // ==========================================
  // CANCEL DRAFT
  // ==========================================

  const cancelDraft = () => {
    setIsCreatingDraft(false)
    setDraftTitle('')
    setContent('')
    setFindings([])
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

  // ==========================================
  // SUBMIT FOR REVIEW
  // ==========================================

  const submitForReview = () => {
    if (content.trim() === '' && !site) {
      return
    }

    const submission: ReviewSubmission = {
      id: Date.now(),
      title: draftTitle.trim() || 'Untitled Draft',
      content: content.trim() || (site ? `Website check: ${site.url}` : ''),
      findings: findings.filter((_, index) => !hidden.has(index)),
      status: 'Pending Review',
      submittedAt: 'just now',
    }

    setSubmissions((currentSubmissions) => [
      submission,
      ...currentSubmissions,
    ])

    setIsCreatingDraft(false)
    setDraftTitle('')
    setContent('')
    setFindings([])
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

    setActivePage('reviewQueue')
  }

  // ==========================================
  // OPEN SUBMISSION
  // ==========================================

  const openSubmission = (submission: ReviewSubmission) => {
    setSelectedSubmission(submission)
    setActivePage('reviewDetail')
  }

  // ==========================================
  // APPROVE SUBMISSION
  // ==========================================

  const approveSubmission = () => {
    if (!selectedSubmission) {
      return
    }

    setSubmissions((currentSubmissions) =>
      currentSubmissions.map((submission) =>
        submission.id === selectedSubmission.id
          ? {
              ...submission,
              status: 'Approved',
            }
          : submission
      )
    )

    setSelectedSubmission(null)
    setActivePage('reviewQueue')
  }

  // ==========================================
  // REQUEST CHANGES
  // ==========================================

  const requestChanges = () => {
    if (!selectedSubmission) {
      return
    }

    if (changeRequestComment.trim() === '') {
      return
    }

    setSubmissions((currentSubmissions) =>
      currentSubmissions.map((submission) =>
        submission.id === selectedSubmission.id
          ? {
              ...submission,
              status: 'Changes Requested',
              reviewerComment: changeRequestComment.trim(),
            }
          : submission
      )
    )

    setChangeRequestComment('')
    setShowChangeRequestModal(false)
    setSelectedSubmission(null)
    setActivePage('reviewQueue')
  }

  return (
    <div className="relative min-h-screen text-white">

      <div className="aurora" aria-hidden="true" />

      {/* ==========================================
          TOP BAR
          ========================================== */}

      <header className="relative z-10 flex h-16 items-center justify-between border-b border-white/5 bg-slate-950/50 px-5 backdrop-blur-xl">

        {/* Sidebar toggle + Logo */}
        <div className="flex items-center gap-3">

          <button
            onClick={() => setSidebarOpen((open) => !open)}
            aria-label={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
            className="btn-ghost flex h-9 w-9 items-center justify-center"
          >
            <Icon name="panel" />
          </button>

          <span className="text-lg font-semibold tracking-tight">
            ENGANO
          </span>

        </div>

        {/* User */}
        <div className="flex items-center gap-3">

          <span className="text-sm text-slate-400">
            Aditya Barua
          </span>

          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-violet-500/40 to-fuchsia-500/30 text-sm font-semibold ring-1 ring-white/10">
            AB
          </div>

        </div>

      </header>

      {/* ==========================================
          MAIN APPLICATION
          ========================================== */}

      <div className="relative z-10 flex min-h-[calc(100vh-4rem)]">

        {/* ==========================================
            SIDEBAR
            ========================================== */}

        <aside
          className={`shrink-0 overflow-hidden border-white/5 bg-slate-950/40 backdrop-blur-xl transition-all duration-300 ${
            sidebarOpen ? 'w-72 border-r p-5' : 'w-0 border-r-0 p-0'
          }`}
        >
          <div className="w-62">

          <p className="mb-4 px-3 text-xs font-semibold uppercase tracking-widest text-slate-500">
            Workspace
          </p>

          <nav className="space-y-1.5">

            {/* Studio */}
            <button
              onClick={() => {
                setActivePage('studio')
                setIsCreatingDraft(false)
              }}
              className={`flex w-full items-center gap-3.5 rounded-xl px-4 py-3.5 text-left text-base font-medium transition-colors ${
                activePage === 'studio'
                  ? 'bg-white/10 text-white ring-1 ring-white/10'
                  : 'text-slate-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Icon name="studio" />
              Studio
            </button>

            {/* Review Queue */}
            <button
              onClick={() => {
                setActivePage('reviewQueue')
                setIsCreatingDraft(false)
              }}
              className={`flex w-full items-center justify-between rounded-xl px-4 py-3.5 text-left text-base font-medium transition-colors ${
                activePage === 'reviewQueue' ||
                activePage === 'reviewDetail'
                  ? 'bg-white/10 text-white ring-1 ring-white/10'
                  : 'text-slate-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <span className="flex items-center gap-3.5">
                <Icon name="queue" />
                Review Queue
              </span>

              {submissions.filter(
                (submission) =>
                  submission.status === 'Pending Review'
              ).length > 0 && (
                <span className="rounded-full bg-violet-500 px-2 py-0.5 text-xs font-bold text-white">
                  {
                    submissions.filter(
                      (submission) =>
                        submission.status === 'Pending Review'
                    ).length
                  }
                </span>
              )}

            </button>

            {/* Approvals */}
            <button
              onClick={() => {
                setActivePage('approvals')
                setIsCreatingDraft(false)
              }}
              className={`flex w-full items-center gap-3.5 rounded-xl px-4 py-3.5 text-left text-base font-medium transition-colors ${
                activePage === 'approvals'
                  ? 'bg-white/10 text-white ring-1 ring-white/10'
                  : 'text-slate-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Icon name="approvals" />
              Approvals
            </button>

            {/* History */}
            <button
              onClick={() => {
                setActivePage('history')
                setIsCreatingDraft(false)
              }}
              className={`flex w-full items-center gap-3.5 rounded-xl px-4 py-3.5 text-left text-base font-medium transition-colors ${
                activePage === 'history'
                  ? 'bg-white/10 text-white ring-1 ring-white/10'
                  : 'text-slate-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Icon name="history" />
              History
            </button>

            {/* Insights */}
            <button
              onClick={() => {
                setActivePage('insights')
                setIsCreatingDraft(false)
              }}
              className={`flex w-full items-center gap-3.5 rounded-xl px-4 py-3.5 text-left text-base font-medium transition-colors ${
                activePage === 'insights'
                  ? 'bg-white/10 text-white ring-1 ring-white/10'
                  : 'text-slate-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Icon name="insights" />
              Insights
            </button>

            {/* Brand Guidelines */}
            <button
              onClick={() => {
                setActivePage('guidelines')
                setIsCreatingDraft(false)
              }}
              className={`flex w-full items-center gap-3.5 rounded-xl px-4 py-3.5 text-left text-base font-medium transition-colors ${
                activePage === 'guidelines'
                  ? 'bg-white/10 text-white ring-1 ring-white/10'
                  : 'text-slate-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Icon name="guidelines" />
              Brand Guidelines
            </button>

          </nav>

          </div>

        </aside>

        {/* ==========================================
            MAIN CONTENT
            ========================================== */}

        <main className="min-w-0 flex-1 p-8">

          {/* ==========================================
              STUDIO
              ========================================== */}

          {activePage === 'studio' && (
            <>

              {/* Empty Studio (hero) */}
              {!isCreatingDraft && (
                <div className="rise mx-auto flex min-h-[calc(100vh-9rem)] max-w-2xl flex-col items-center justify-center text-center">

                  <h2 className="text-4xl font-semibold tracking-tight">
                    What are we reviewing today?
                  </h2>

                  <p className="mt-3 max-w-md text-sm text-slate-400">
                    Paste a post, email or announcement and ENGANO checks it against your brand guidelines.
                  </p>

                  <button
                    onClick={createNewDraft}
                    className="composer mt-10 w-full cursor-text p-5 text-left"
                  >

                    <p className="text-base text-slate-500">
                      Paste or write your content…
                    </p>

                    <div className="mt-10 flex items-center justify-between">

                      <span className="flex items-center gap-2 text-xs text-slate-400">
                        <span className="rounded-full border border-white/10 px-2.5 py-1">Brand rules</span>
                        <span className="rounded-full border border-white/10 px-2.5 py-1">AI agents</span>
                      </span>

                      <span className="btn-primary px-4 py-2 text-sm">
                        Create draft
                      </span>

                    </div>

                  </button>

                  <p className="mt-5 flex items-center gap-2 text-xs text-slate-500">
                    <Icon name="lock" className="h-3.5 w-3.5" />
                    Checked against your brand policy. Nothing is published from here.
                  </p>

                </div>
              )}

              {/* Compose + conversation */}
              {isCreatingDraft && (
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
                  onCancel={cancelDraft}
                  onSubmit={submitForReview}
                />
              )}

            </>
          )}

          {/* ==========================================
              REVIEW QUEUE
              ========================================== */}

          {activePage === 'reviewQueue' && (
            <ReviewQueue
              submissions={submissions}
              onOpenSubmission={openSubmission}
            />
          )}

          {/* ==========================================
              REVIEW DETAIL
              ========================================== */}

          {activePage === 'reviewDetail' && selectedSubmission && (
            <div>

              {/* Header */}
              <div className="mb-8 flex items-center justify-between">

                <div>

                  <button
                    onClick={() => setActivePage('reviewQueue')}
                    className="mb-4 text-sm text-slate-400 hover:text-white"
                  >
                    ← Back to Review Queue
                  </button>

                  <h1 className="text-2xl font-semibold">
                    Review Submission
                  </h1>

                  <p className="mt-1 text-sm text-slate-400">
                    Review the content and ENGANO findings before making a decision.
                  </p>

                </div>

                <span className="rounded-full bg-yellow-400/10 px-3 py-1.5 text-sm font-medium text-yellow-300">
                  Pending Review
                </span>

              </div>

              {/* Submission */}
              <div className="mb-6 glass rounded-2xl p-6">

                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Submission
                </p>

                <h2 className="mt-2 text-xl font-semibold">
                  {selectedSubmission.title}
                </h2>

                <p className="mt-1 text-sm text-slate-500">
                  Submitted {selectedSubmission.submittedAt}
                </p>

              </div>

              {/* Content */}
              <div className="mb-6 glass rounded-2xl p-6">

                <h2 className="text-lg font-semibold">
                  Content
                </h2>

                <div className="mt-4 rounded-lg bg-slate-950 p-5">

                  <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">
                    {selectedSubmission.content}
                  </p>

                </div>

              </div>

              {/* Findings */}
              <div>

                <div className="mb-4">

                  <h2 className="text-lg font-semibold">
                    ENGANO Findings
                  </h2>

                  <p className="mt-1 text-sm text-slate-400">
                    Automated findings that should be considered before approval.
                  </p>

                </div>

                <div className="space-y-4">

                  {selectedSubmission.findings.map((finding, index) => (

                    <div
                      key={index}
                      className="glass rounded-2xl p-5"
                    >

                      {/* Finding Header */}
                      <div className="flex items-start gap-3">

                        <div
                          className={`mt-1 h-3 w-3 shrink-0 rounded-full ${
                            finding.severity === 'Critical'
                              ? 'bg-red-500'
                              : finding.severity === 'Warning'
                                ? 'bg-yellow-400'
                                : 'bg-blue-400'
                          }`}
                        />

                        <div>

                          <div className="flex flex-wrap items-center gap-2">

                            <h3 className="font-semibold">
                              {finding.issue}
                            </h3>

                            <span
                              className={`rounded-full px-2 py-1 text-xs font-medium ${
                                finding.severity === 'Critical'
                                  ? 'bg-red-500/10 text-red-400'
                                  : finding.severity === 'Warning'
                                    ? 'bg-yellow-400/10 text-yellow-300'
                                    : 'bg-blue-400/10 text-blue-300'
                              }`}
                            >
                              {finding.severity}
                            </span>

                          </div>

                          <p className="mt-1 text-xs text-slate-500">
                            {finding.category}
                          </p>

                        </div>

                      </div>

                      {/* Explanation */}
                      <div className="mt-5 rounded-lg bg-slate-950/70 p-4">

                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                          Why ENGANO flagged this
                        </p>

                        <p className="mt-2 text-sm leading-6 text-slate-300">
                          {finding.explanation}
                        </p>

                      </div>

                      {/* Guideline */}
                      <div className="mt-3 rounded-lg border border-white/10 p-4">

                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                          Guideline involved
                        </p>

                        <p className="mt-2 text-sm leading-6 text-slate-300">
                          {finding.guideline}
                        </p>

                      </div>

                      {/* Suggested Correction */}
                      <div className="mt-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">

                        <p className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                          Suggested correction
                        </p>

                        <p className="mt-2 text-sm leading-6 text-slate-300">
                          {finding.suggestion}
                        </p>

                      </div>

                    </div>

                  ))}

                </div>

              </div>

              {/* Reviewer Decision */}
              <div className="mt-8 glass rounded-2xl p-6">

                <div className="flex items-center justify-between gap-6">

                  <div>

                    <h2 className="font-semibold">
                      Reviewer Decision
                    </h2>

                    <p className="mt-1 text-sm text-slate-400">
                      Choose how this submission should proceed.
                    </p>

                  </div>

                  <div className="flex gap-3">

                    <button
                      onClick={() => setShowChangeRequestModal(true)}
                      className="rounded-lg border border-red-500/30 bg-red-500/5 px-5 py-3 text-sm font-semibold text-red-400 hover:bg-red-500/10"
                    >
                      Request Changes
                    </button>

                    <button
                      onClick={approveSubmission}
                      className="btn-primary px-5 py-3 text-sm"
                    >
                      Approve
                    </button>

                  </div>

                </div>

              </div>

              {/* Request Changes Modal */}
              {showChangeRequestModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
                  <div className="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">

                    <div className="flex items-start justify-between">

                      <div>
                        <h2 className="text-lg font-semibold">
                          Request Changes
                        </h2>

                        <p className="mt-1 text-sm text-slate-400">
                          Tell the creator what needs to be changed before this content can be approved.
                        </p>
                      </div>

                      <button
                        onClick={() => {
                          setShowChangeRequestModal(false)
                          setChangeRequestComment('')
                        }}
                        className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-800 hover:text-white"
                      >
                        ✕
                      </button>

                    </div>

                    <div className="mt-6">

                      <label className="mb-2 block text-sm font-medium text-slate-300">
                        Reason for changes
                      </label>

                      <textarea
                        rows={5}
                        value={changeRequestComment}
                        onChange={(event) =>
                          setChangeRequestComment(event.target.value)
                        }
                        placeholder="e.g. Please remove the unsupported performance claim and replace it with an approved statement."
                        className="w-full resize-none rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm leading-6 text-white outline-none placeholder:text-slate-600 focus:border-red-500"
                      />

                    </div>

                    <div className="mt-6 flex justify-end gap-3">

                      <button
                        onClick={() => {
                          setShowChangeRequestModal(false)
                          setChangeRequestComment('')
                        }}
                        className="rounded-lg border border-slate-700 px-4 py-2.5 text-sm font-medium text-slate-300 hover:bg-slate-800"
                      >
                        Cancel
                      </button>

                      <button
                        onClick={requestChanges}
                        disabled={changeRequestComment.trim() === ''}
                        className="rounded-lg bg-red-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-400 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Request Changes
                      </button>

                    </div>

                  </div>
                </div>
              )}

            </div>
          )}

          {/* ==========================================
              APPROVALS
              ========================================== */}

          {activePage === 'approvals' && (
            <Approvals
              submissions={submissions}
            />
          )}

          {/* ==========================================
              HISTORY
              ========================================== */}

          {activePage === 'history' && (
            <History
              submissions={submissions}
            />
          )}

          {/* ==========================================
              INSIGHTS
              ========================================== */}

          {activePage === 'insights' && (
            <Insights
              submissions={submissions}
            />
          )}

          {/* ==========================================
              BRAND GUIDELINES
              ========================================== */}

          {activePage === 'guidelines' && (
            <BrandGuidelines
              guidelines={guidelines}
              setGuidelines={setGuidelines}
            />
          )}

        </main>

      </div>

    </div>
  )
}

export default App
