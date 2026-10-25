import type { Finding } from '../App'

export type ReviewSubmission = {
  id: number
  title: string
  content: string
  findings: Finding[]
  status: 'Pending Review' | 'Approved' | 'Changes Requested'
  submittedAt: string
  reviewerComment?: string
  // Workspace flow: who wrote it, where it belongs, who cleared it.
  workspaceId?: number | null
  creatorId?: string
  approvedBy?: 'AI' | 'Reviewer' | 'Brand Manager'
  published?: boolean
  aiStatus?: 'GREEN' | 'YELLOW' | 'RED'
  at?: number
  // Revision history: how many versions were sent, and how many comments there are.
  version?: number
  comments?: number
}

type ReviewQueueProps = {
  submissions: ReviewSubmission[]
  onOpenSubmission: (submission: ReviewSubmission) => void
}

function ReviewQueue({
  submissions,
  onOpenSubmission,
}: ReviewQueueProps) {
  const getHighestSeverity = (findings: Finding[]) => {
    if (findings.some((finding) => finding.severity === 'Critical')) {
      return 'Critical'
    }

    if (findings.some((finding) => finding.severity === 'Warning')) {
      return 'Warning'
    }

    return 'Suggestion'
  }

  const getSeverityClasses = (severity: string) => {
    if (severity === 'Critical') {
      return 'bg-red-500/10 text-red-400'
    }

    if (severity === 'Warning') {
      return 'bg-yellow-400/10 text-yellow-300'
    }

    return 'bg-blue-400/10 text-blue-300'
  }

  const pendingSubmissions = submissions.filter(
    (submission) => submission.status === 'Pending Review'
  )

  const changesRequestedSubmissions = submissions.filter(
    (submission) => submission.status === 'Changes Requested'
  )

  return (
    <div>

      {/* Header */}
      <div className="mb-8 flex items-center justify-between">

        <div>
          <h1 className="text-2xl font-semibold">
            Review Queue
          </h1>

          <p className="mt-1 text-sm text-slate-400">
            Review content submitted for brand governance approval.
          </p>
        </div>

        <div className="rounded-lg glass px-4 py-2">
          <span className="text-sm text-slate-400">
            Pending
          </span>

          <span className="ml-2 font-semibold text-white">
            {pendingSubmissions.length}
          </span>
        </div>

      </div>

      {/* Changes Requested */}
      {changesRequestedSubmissions.length > 0 && (
        <div className="mb-8">

          <div className="mb-4">
            <h2 className="text-lg font-semibold">
              Changes Requested
            </h2>

            <p className="mt-1 text-sm text-slate-400">
              These submissions need updates based on reviewer feedback.
            </p>
          </div>

          <div className="space-y-4">

            {changesRequestedSubmissions.map((submission) => (
              <div
                key={submission.id}
                className="rounded-xl border border-red-500/20 bg-red-500/5 p-5"
              >

                <div className="flex items-start justify-between gap-6">

                  <div className="min-w-0 flex-1">

                    <div className="flex flex-wrap items-center gap-3">

                      <h2 className="text-lg font-semibold">
                        {submission.title || 'Untitled Draft'}
                      </h2>

                      <span className="rounded-full bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-400">
                        Changes Requested
                      </span>

                    </div>

                    <p className="mt-2 text-sm text-slate-500">
                      Submitted {submission.submittedAt}
                    </p>

                    {/* Reviewer Feedback */}
                    <div className="mt-5 rounded-lg border border-red-500/20 bg-slate-950/60 p-4">

                      <p className="text-xs font-semibold uppercase tracking-wider text-red-400">
                        Reviewer Feedback
                      </p>

                      <p className="mt-2 text-sm leading-6 text-slate-300">
                        {submission.reviewerComment ||
                          'The reviewer requested changes to this submission.'}
                      </p>

                    </div>

                    {/* Content Preview */}
                    <div className="mt-4 rounded-lg bg-slate-950/70 p-4">

                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Current Content
                      </p>

                      <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-300">
                        {submission.content}
                      </p>

                    </div>

                  </div>

                  <button
                    onClick={() => onOpenSubmission(submission)}
                    className="shrink-0 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-semibold text-red-400 hover:bg-red-500/20"
                  >
                    Open Submission
                  </button>

                </div>

              </div>
            ))}

          </div>

        </div>
      )}

      {/* Empty State */}
      {pendingSubmissions.length === 0 &&
        changesRequestedSubmissions.length === 0 && (
          <div className="flex min-h-[400px] items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-900/40">

            <div className="text-center">

              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-slate-800 text-2xl">
                ✓
              </div>

              <h2 className="text-lg font-medium">
                Review queue is empty
              </h2>

              <p className="mt-2 max-w-sm text-sm text-slate-400">
                Content submitted from Studio will appear here for review.
              </p>

            </div>

          </div>
        )}

      {/* Pending Review Queue */}
      {pendingSubmissions.length > 0 && (
        <div>

          <div className="mb-4">
            <h2 className="text-lg font-semibold">
              Pending Review
            </h2>

            <p className="mt-1 text-sm text-slate-400">
              Content waiting for a reviewer decision.
            </p>
          </div>

          <div className="space-y-4">

            {pendingSubmissions.map((submission) => {

              const highestSeverity = getHighestSeverity(
                submission.findings
              )

              return (
                <div
                  key={submission.id}
                  className="glass rounded-2xl p-5"
                >

                  <div className="flex items-start justify-between gap-6">

                    <div className="min-w-0 flex-1">

                      {/* Title */}
                      <div className="flex flex-wrap items-center gap-3">

                        <h2 className="text-lg font-semibold">
                          {submission.title || 'Untitled Draft'}
                        </h2>

                        <span className="rounded-full bg-yellow-400/10 px-2.5 py-1 text-xs font-medium text-yellow-300">
                          Pending Review
                        </span>

                      </div>

                      <p className="mt-2 text-sm text-slate-500">
                        Submitted {submission.submittedAt}
                      </p>

                      {/* Summary */}
                      <div className="mt-5 flex flex-wrap gap-3">

                        <div className="rounded-lg border border-white/10 bg-slate-950/60 px-4 py-3">
                          <p className="text-xs text-slate-500">
                            Findings
                          </p>

                          <p className="mt-1 font-semibold text-white">
                            {submission.findings.length}
                          </p>
                        </div>

                        <div className="rounded-lg border border-white/10 bg-slate-950/60 px-4 py-3">
                          <p className="text-xs text-slate-500">
                            Highest severity
                          </p>

                          <span
                            className={`mt-1 inline-block rounded-full px-2 py-1 text-xs font-medium ${getSeverityClasses(
                              highestSeverity
                            )}`}
                          >
                            {highestSeverity}
                          </span>
                        </div>

                      </div>

                      {/* Preview */}
                      <div className="mt-5 rounded-lg bg-slate-950/70 p-4">

                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                          Content preview
                        </p>

                        <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-300">
                          {submission.content}
                        </p>

                      </div>

                    </div>

                    {/* Open Review */}
                    <button
                      onClick={() => onOpenSubmission(submission)}
                      className="shrink-0 btn-primary px-4 py-2.5 text-sm"
                    >
                      Open Review
                    </button>

                  </div>

                </div>
              )
            })}

          </div>

        </div>
      )}

    </div>
  )
}

export default ReviewQueue
