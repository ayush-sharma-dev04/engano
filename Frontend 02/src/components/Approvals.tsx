import type { ReviewSubmission } from './ReviewQueue'

type ApprovalsProps = {
  submissions: ReviewSubmission[]
}

function Approvals({ submissions }: ApprovalsProps) {
  const approvedSubmissions = submissions.filter(
    (submission) => submission.status === 'Approved'
  )

  return (
    <div>

      {/* Header */}
      <div className="mb-8">

        <h1 className="text-2xl font-semibold">
          Approvals
        </h1>

        <p className="mt-1 text-sm text-slate-400">
          Content that has passed human review and received approval.
        </p>

      </div>


      {/* Summary */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">

        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">

          <p className="text-sm text-slate-500">
            Total Approved
          </p>

          <p className="mt-2 text-2xl font-semibold text-emerald-400">
            {approvedSubmissions.length}
          </p>

        </div>


        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">

          <p className="text-sm text-slate-500">
            With Findings
          </p>

          <p className="mt-2 text-2xl font-semibold">
            {
              approvedSubmissions.filter(
                (submission) => submission.findings.length > 0
              ).length
            }
          </p>

        </div>


        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">

          <p className="text-sm text-slate-500">
            Clean Reviews
          </p>

          <p className="mt-2 text-2xl font-semibold">
            {
              approvedSubmissions.filter(
                (submission) =>
                  submission.findings.length === 1 &&
                  submission.findings[0]?.severity === 'Suggestion'
              ).length
            }
          </p>

        </div>

      </div>


      {/* Empty State */}
      {approvedSubmissions.length === 0 && (
        <div className="flex min-h-[400px] items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-900/40">

          <div className="text-center">

            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-slate-800 text-2xl">
              ✓
            </div>

            <h2 className="text-lg font-medium">
              No approved content yet
            </h2>

            <p className="mt-2 max-w-sm text-sm text-slate-400">
              Content approved through the Review Queue will appear here.
            </p>

          </div>

        </div>
      )}


      {/* Approved Content */}
      {approvedSubmissions.length > 0 && (
        <div className="space-y-4">

          {approvedSubmissions.map((submission) => (

            <div
              key={submission.id}
              className="rounded-xl border border-slate-800 bg-slate-900/50 p-6"
            >

              {/* Header */}
              <div className="flex items-start justify-between gap-6">

                <div>

                  <div className="flex flex-wrap items-center gap-3">

                    <h2 className="text-lg font-semibold">
                      {submission.title}
                    </h2>

                    <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
                      Approved
                    </span>

                  </div>

                  <p className="mt-2 text-sm text-slate-500">
                    Approved after ENGANO review
                  </p>

                </div>


                <div className="shrink-0 text-right">

                  <p className="text-xs text-slate-500">
                    Submitted
                  </p>

                  <p className="mt-1 text-sm text-slate-300">
                    {submission.submittedAt}
                  </p>

                </div>

              </div>


              {/* Findings Summary */}
              <div className="mt-5 flex flex-wrap gap-3">

                <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-3">

                  <p className="text-xs text-slate-500">
                    Findings reviewed
                  </p>

                  <p className="mt-1 font-semibold">
                    {submission.findings.length}
                  </p>

                </div>


                <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-3">

                  <p className="text-xs text-slate-500">
                    Decision
                  </p>

                  <p className="mt-1 font-semibold text-emerald-400">
                    Approved
                  </p>

                </div>

              </div>


              {/* Content */}
              <div className="mt-5 rounded-lg bg-slate-950/70 p-5">

                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Approved Content
                </p>

                <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-300">
                  {submission.content}
                </p>

              </div>


              {/* Findings */}
              {submission.findings.length > 0 && (
                <div className="mt-5">

                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    ENGANO Findings Reviewed
                  </p>

                  <div className="mt-3 space-y-2">

                    {submission.findings.map((finding, index) => (

                      <div
                        key={index}
                        className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/40 px-4 py-3"
                      >

                        <div
                          className={`h-2.5 w-2.5 rounded-full ${
                            finding.severity === 'Critical'
                              ? 'bg-red-500'
                              : finding.severity === 'Warning'
                                ? 'bg-yellow-400'
                                : 'bg-blue-400'
                          }`}
                        />

                        <span className="text-sm text-slate-300">
                          {finding.issue}
                        </span>

                        <span
                          className={`ml-auto rounded-full px-2 py-1 text-xs ${
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

                    ))}

                  </div>

                </div>
              )}

            </div>

          ))}

        </div>
      )}

    </div>
  )
}

export default Approvals