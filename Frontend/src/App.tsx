import { useState } from 'react'
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
}

export type Guideline = {
  id: number
  type: 'DO' | "DON'T"
  text: string
}

function App() {
  const [activePage, setActivePage] = useState('studio')

  const [isCreatingDraft, setIsCreatingDraft] = useState(false)
  const [isReviewing, setIsReviewing] = useState(false)

  const [draftTitle, setDraftTitle] = useState('')
  const [content, setContent] = useState('')

  const [findings, setFindings] = useState<Finding[]>([])

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

  const runReview = () => {
    setIsReviewing(true)

    const newFindings: Finding[] = []

    const lowerContent = content.toLowerCase()

    // ==========================================
    // BUILT-IN DEMONSTRATION RULES
    // ==========================================

    // Check 1: Unsupported superlative claims
    if (
      lowerContent.includes('fastest') ||
      lowerContent.includes('best in the world') ||
      lowerContent.includes('#1')
    ) {
      newFindings.push({
        severity: 'Critical',
        category: 'Unsupported Claim',
        issue: 'Potential unsupported promotional claim',
        explanation:
          'The content contains a strong promotional claim that may require an approved source or benchmark.',
        guideline:
          'Avoid superlative claims unless they are supported by an approved source.',
        suggestion:
          'Replace the claim with a factual statement that can be verified.',
      })
    }

    // Check 2: Free forever
    if (
      lowerContent.includes('free forever') ||
      lowerContent.includes('100% free')
    ) {
      newFindings.push({
        severity: 'Warning',
        category: 'Promotional Language',
        issue: 'Potentially misleading promotional wording',
        explanation:
          'This wording may create a stronger promise than the approved product information supports.',
        guideline:
          'Do not make promotional promises that are not present in the approved product information.',
        suggestion:
          'Use the exact approved pricing or offer language instead.',
      })
    }

    // Check 3: Terminology
    if (
      lowerContent.includes('nimbusdb') ||
      lowerContent.includes('nimbus database')
    ) {
      newFindings.push({
        severity: 'Warning',
        category: 'Terminology',
        issue: 'Non-approved product terminology',
        explanation:
          'The product name does not match the preferred terminology stored in the Brand Library.',
        guideline:
          'Use the approved product name: "Nimbus DB".',
        suggestion:
          'Replace the incorrect product name with "Nimbus DB".',
      })
    }

    // Check 4: Guaranteed language
    if (
      lowerContent.includes('guaranteed') ||
      lowerContent.includes('guarantee')
    ) {
      newFindings.push({
        severity: 'Warning',
        category: 'Claims',
        issue: 'Guarantee language detected',
        explanation:
          'Guarantee-based language can create a claim that requires explicit approval or supporting evidence.',
        guideline:
          'Avoid guarantees unless they are explicitly approved.',
        suggestion:
          'Rewrite the statement as a factual product capability.',
      })
    }

    // ==========================================
    // CUSTOM BRAND GUIDELINES
    // ==========================================

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

    // ==========================================
    // NO ISSUES
    // ==========================================

    if (newFindings.length === 0) {
      newFindings.push({
        severity: 'Suggestion',
        category: 'Brand Check',
        issue: 'No major issues detected',
        explanation:
          'ENGANO did not detect any of the currently configured demonstration rules or brand guideline conflicts in this content.',
        guideline:
          'Continue following the approved brand guidelines and source material.',
        suggestion:
          'Content can proceed to human review.',
      })
    }

    setFindings(newFindings)
    setIsReviewing(false)
  }

  // ==========================================
  // CREATE NEW DRAFT
  // ==========================================

  const createNewDraft = () => {
    setDraftTitle('')
    setContent('')
    setFindings([])
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
  }

  // ==========================================
  // SUBMIT FOR REVIEW
  // ==========================================

  const submitForReview = () => {
    if (content.trim() === '') {
      return
    }

    const submission: ReviewSubmission = {
      id: Date.now(),
      title: draftTitle.trim() || 'Untitled Draft',
      content: content.trim(),
      findings,
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
    <div className="min-h-screen bg-slate-950 text-white">

      {/* ==========================================
          TOP BAR
          ========================================== */}

      <header className="flex h-16 items-center justify-between border-b border-slate-800 px-6">

        {/* Logo */}
        <div className="flex items-center gap-3">

          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500 font-bold text-slate-950">
            E
          </div>

          <span className="text-xl font-bold tracking-tight">
            ENGANO
          </span>

        </div>

        {/* User */}
        <div className="flex items-center gap-3">

          <span className="text-sm text-slate-400">
            Aditya Barua
          </span>

          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-sm font-semibold">
            AB
          </div>

        </div>

      </header>

      {/* ==========================================
          MAIN APPLICATION
          ========================================== */}

      <div className="flex min-h-[calc(100vh-4rem)]">

        {/* ==========================================
            SIDEBAR
            ========================================== */}

        <aside className="w-60 border-r border-slate-800 bg-slate-950 p-4">

          <p className="mb-4 px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Workspace
          </p>

          <nav className="space-y-1">

            {/* Studio */}
            <button
              onClick={() => {
                setActivePage('studio')
                setIsCreatingDraft(false)
              }}
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm font-medium ${
                activePage === 'studio'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-white'
              }`}
            >
              Studio
            </button>

            {/* Review Queue */}
            <button
              onClick={() => {
                setActivePage('reviewQueue')
                setIsCreatingDraft(false)
              }}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm font-medium ${
                activePage === 'reviewQueue' ||
                activePage === 'reviewDetail'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-white'
              }`}
            >
              <span>
                Review Queue
              </span>

              {submissions.filter(
                (submission) =>
                  submission.status === 'Pending Review'
              ).length > 0 && (
                <span className="rounded-full bg-emerald-500 px-2 py-0.5 text-xs font-bold text-slate-950">
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
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm font-medium ${
                activePage === 'approvals'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-white'
              }`}
            >
              Approvals
            </button>

            {/* History */}
            <button
              onClick={() => {
                setActivePage('history')
                setIsCreatingDraft(false)
              }}
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm font-medium ${
                activePage === 'history'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-white'
              }`}
            >
              History
            </button>

            {/* Insights */}
            <button
              onClick={() => {
                setActivePage('insights')
                setIsCreatingDraft(false)
              }}
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm font-medium ${
                activePage === 'insights'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-white'
              }`}
            >
              Insights
            </button>

            {/* Brand Guidelines */}
            <button
              onClick={() => {
                setActivePage('guidelines')
                setIsCreatingDraft(false)
              }}
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm font-medium ${
                activePage === 'guidelines'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-white'
              }`}
            >
              Brand Guidelines
            </button>

          </nav>

        </aside>

        {/* ==========================================
            MAIN CONTENT
            ========================================== */}

        <main className="flex-1 p-8">

          {/* ==========================================
              STUDIO
              ========================================== */}

          {activePage === 'studio' && (
            <>

              {/* Studio Header */}
              <div className="mb-8">

                <h1 className="text-2xl font-semibold">
                  Studio
                </h1>

                <p className="mt-1 text-sm text-slate-400">
                  Review your content before it goes public.
                </p>

              </div>

              {/* Empty Studio */}
              {!isCreatingDraft && (
                <div className="flex min-h-[500px] items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-900/40">

                  <div className="text-center">

                    <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-slate-800 text-2xl">
                      ✦
                    </div>

                    <h2 className="text-lg font-medium">
                      Start a brand review
                    </h2>

                    <p className="mt-2 max-w-sm text-sm text-slate-400">
                      Create or paste content and ENGANO will check it against your brand guidelines.
                    </p>

                    <button
                      onClick={createNewDraft}
                      className="mt-6 rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
                    >
                      Create Draft
                    </button>

                  </div>

                </div>
              )}

              {/* Draft Editor */}
              {isCreatingDraft && (
                <div>

                  <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">

                    {/* Editor Header */}
                    <div className="mb-6 flex items-center justify-between">

                      <div>

                        <h2 className="text-lg font-semibold">
                          New Draft
                        </h2>

                        <p className="mt-1 text-sm text-slate-400">
                          Write or paste content to begin a brand review.
                        </p>

                      </div>

                      <button
                        onClick={cancelDraft}
                        className="rounded-lg px-3 py-2 text-sm text-slate-400 hover:bg-slate-800 hover:text-white"
                      >
                        Cancel
                      </button>

                    </div>

                    {/* Draft Title */}
                    <div className="mb-4">

                      <label className="mb-2 block text-sm font-medium text-slate-300">
                        Draft title
                      </label>

                      <input
                        type="text"
                        value={draftTitle}
                        onChange={(event) =>
                          setDraftTitle(event.target.value)
                        }
                        placeholder="e.g. Nimbus DB Launch Campaign"
                        className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-emerald-500"
                      />

                    </div>

                    {/* Content */}
                    <div>

                      <label className="mb-2 block text-sm font-medium text-slate-300">
                        Content
                      </label>

                      <textarea
                        rows={12}
                        value={content}
                        onChange={(event) =>
                          setContent(event.target.value)
                        }
                        placeholder="Paste or write your content here..."
                        className="w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm leading-6 text-white outline-none placeholder:text-slate-600 focus:border-emerald-500"
                      />

                    </div>

                    {/* Buttons */}
                    <div className="mt-5 flex justify-end gap-3">

                      <button
                        onClick={runReview}
                        disabled={
                          isReviewing ||
                          content.trim() === ''
                        }
                        className="rounded-lg border border-slate-700 px-5 py-2.5 text-sm font-semibold text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {isReviewing
                          ? 'Reviewing...'
                          : 'Run ENGANO Review'}
                      </button>

                    </div>

                  </div>

                  {/* Review Results */}
                  {findings.length > 0 && (
                    <div className="mt-6">

                      <div className="mb-4">

                        <h2 className="text-xl font-semibold">
                          ENGANO Findings
                        </h2>

                        <p className="mt-1 text-sm text-slate-400">
                          Issues detected during the brand governance review.
                        </p>

                      </div>

                      <div className="space-y-4">

                        {findings.map((finding, index) => (

                          <div
                            key={index}
                            className="rounded-xl border border-slate-800 bg-slate-900/60 p-5"
                          >

                            {/* Finding Header */}
                            <div className="flex items-start gap-3">

                              <div
                                className={`mt-1 h-3 w-3 rounded-full ${
                                  finding.severity === 'Critical'
                                    ? 'bg-red-500'
                                    : finding.severity === 'Warning'
                                      ? 'bg-yellow-400'
                                      : 'bg-blue-400'
                                }`}
                              />

                              <div className="flex-1">

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
                            <div className="mt-3 rounded-lg border border-slate-800 p-4">

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

                      {/* Submit Button */}
                      <div className="mt-6 flex justify-end">

                        <button
                          onClick={submitForReview}
                          className="rounded-lg bg-emerald-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
                        >
                          Submit for Review
                        </button>

                      </div>

                    </div>
                  )}

                </div>
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
              <div className="mb-6 rounded-xl border border-slate-800 bg-slate-900/50 p-6">

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
              <div className="mb-6 rounded-xl border border-slate-800 bg-slate-900/50 p-6">

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
                      className="rounded-xl border border-slate-800 bg-slate-900/60 p-5"
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
                      <div className="mt-3 rounded-lg border border-slate-800 p-4">

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
              <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900/60 p-6">

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
                      className="rounded-lg bg-emerald-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
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
                        className="w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm leading-6 text-white outline-none placeholder:text-slate-600 focus:border-red-500"
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
