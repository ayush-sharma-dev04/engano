import type { ReviewSubmission } from './ReviewQueue'

type InsightsProps = {
  submissions: ReviewSubmission[]
}

function Insights({ submissions }: InsightsProps) {

  const totalReviews = submissions.length

  const approved = submissions.filter(
    (submission) => submission.status === 'Approved'
  ).length

  const changesRequested = submissions.filter(
    (submission) => submission.status === 'Changes Requested'
  ).length

  const pending = submissions.filter(
    (submission) => submission.status === 'Pending Review'
  ).length

  const criticalFindings = submissions.reduce(
    (total, submission) =>
      total +
      submission.findings.filter(
        (finding) => finding.severity === 'Critical'
      ).length,
    0
  )

  const warningFindings = submissions.reduce(
    (total, submission) =>
      total +
      submission.findings.filter(
        (finding) => finding.severity === 'Warning'
      ).length,
    0
  )

  const suggestionFindings = submissions.reduce(
    (total, submission) =>
      total +
      submission.findings.filter(
        (finding) => finding.severity === 'Suggestion'
      ).length,
    0
  )

  const approvalRate =
    totalReviews > 0
      ? Math.round((approved / totalReviews) * 100)
      : 0

  return (
    <div>

      {/* Header */}
      <div className="mb-8">

        <h1 className="text-2xl font-semibold">
          Insights
        </h1>

        <p className="mt-1 text-sm text-slate-400">
          Understand review activity, decisions, and recurring content risks.
        </p>

      </div>


      {/* Main Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">

        <div className="glass rounded-2xl p-5">

          <p className="text-sm text-slate-500">
            Total Reviews
          </p>

          <p className="mt-2 text-3xl font-semibold">
            {totalReviews}
          </p>

        </div>


        <div className="glass rounded-2xl p-5">

          <p className="text-sm text-slate-500">
            Approved
          </p>

          <p className="mt-2 text-3xl font-semibold text-emerald-400">
            {approved}
          </p>

        </div>


        <div className="glass rounded-2xl p-5">

          <p className="text-sm text-slate-500">
            Changes Requested
          </p>

          <p className="mt-2 text-3xl font-semibold text-red-400">
            {changesRequested}
          </p>

        </div>


        <div className="glass rounded-2xl p-5">

          <p className="text-sm text-slate-500">
            Pending Review
          </p>

          <p className="mt-2 text-3xl font-semibold text-yellow-300">
            {pending}
          </p>

        </div>

      </div>


      {/* Second Row */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">

        {/* Approval Rate */}
        <div className="glass rounded-2xl p-6">

          <h2 className="text-lg font-semibold">
            Approval Rate
          </h2>

          <p className="mt-1 text-sm text-slate-400">
            Percentage of submitted content that has been approved.
          </p>


          <div className="mt-8 flex items-end gap-4">

            <span className="text-5xl font-bold text-emerald-400">
              {approvalRate}%
            </span>

            <span className="pb-2 text-sm text-slate-500">
              of all reviews
            </span>

          </div>


          <div className="mt-6 h-3 overflow-hidden rounded-full bg-slate-800">

            <div
              className="h-full rounded-full bg-emerald-500 transition-all"
              style={{
                width: `${approvalRate}%`,
              }}
            />

          </div>

        </div>


        {/* Findings */}
        <div className="glass rounded-2xl p-6">

          <h2 className="text-lg font-semibold">
            Finding Severity
          </h2>

          <p className="mt-1 text-sm text-slate-400">
            Issues detected across submitted content.
          </p>


          <div className="mt-6 space-y-4">

            {/* Critical */}
            <div>

              <div className="mb-2 flex justify-between text-sm">

                <span className="text-slate-300">
                  Critical
                </span>

                <span className="text-red-400">
                  {criticalFindings}
                </span>

              </div>

              <div className="h-2 rounded-full bg-slate-800">

                <div
                  className="h-full rounded-full bg-red-500"
                  style={{
                    width:
                      criticalFindings > 0
                        ? `${Math.min(
                            criticalFindings * 15,
                            100
                          )}%`
                        : '0%',
                  }}
                />

              </div>

            </div>


            {/* Warning */}
            <div>

              <div className="mb-2 flex justify-between text-sm">

                <span className="text-slate-300">
                  Warning
                </span>

                <span className="text-yellow-400">
                  {warningFindings}
                </span>

              </div>

              <div className="h-2 rounded-full bg-slate-800">

                <div
                  className="h-full rounded-full bg-yellow-400"
                  style={{
                    width:
                      warningFindings > 0
                        ? `${Math.min(
                            warningFindings * 15,
                            100
                          )}%`
                        : '0%',
                  }}
                />

              </div>

            </div>


            {/* Suggestion */}
            <div>

              <div className="mb-2 flex justify-between text-sm">

                <span className="text-slate-300">
                  Suggestion
                </span>

                <span className="text-blue-400">
                  {suggestionFindings}
                </span>

              </div>

              <div className="h-2 rounded-full bg-slate-800">

                <div
                  className="h-full rounded-full bg-blue-400"
                  style={{
                    width:
                      suggestionFindings > 0
                        ? `${Math.min(
                            suggestionFindings * 15,
                            100
                          )}%`
                        : '0%',
                  }}

                />

              </div>

            </div>

          </div>

        </div>

      </div>


      {/* Governance Overview */}
      <div className="mt-6 glass rounded-2xl p-6">

        <h2 className="text-lg font-semibold">
          Governance Overview
        </h2>

        <p className="mt-1 text-sm text-slate-400">
          Current state of content governance across ENGANO.
        </p>


        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">

          <div className="rounded-lg border border-white/10 bg-slate-950/50 p-4">

            <p className="text-xs uppercase tracking-wider text-slate-500">
              Reviews Completed
            </p>

            <p className="mt-2 text-xl font-semibold">
              {approved + changesRequested}
            </p>

          </div>


          <div className="rounded-lg border border-white/10 bg-slate-950/50 p-4">

            <p className="text-xs uppercase tracking-wider text-slate-500">
              Issues Detected
            </p>

            <p className="mt-2 text-xl font-semibold">
              {criticalFindings + warningFindings}
            </p>

          </div>


          <div className="rounded-lg border border-white/10 bg-slate-950/50 p-4">

            <p className="text-xs uppercase tracking-wider text-slate-500">
              Review Completion
            </p>

            <p className="mt-2 text-xl font-semibold text-emerald-400">
              {totalReviews > 0
                ? Math.round(
                    ((approved + changesRequested) /
                      totalReviews) *
                      100
                  )
                : 0}
              %
            </p>

          </div>

        </div>

      </div>


      {/* Empty State */}
      {totalReviews === 0 && (
        <div className="mt-6 rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-8 text-center">

          <p className="text-sm text-slate-400">
            Submit content for review to start generating insights.
          </p>

        </div>
      )}

    </div>
  )
}

export default Insights