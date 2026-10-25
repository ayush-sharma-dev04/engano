import type { ReviewSubmission } from './ReviewQueue'

type HistoryProps = {
  submissions: ReviewSubmission[]
}

function History({ submissions }: HistoryProps) {
  const historySubmissions = submissions.filter(
    (submission) =>
      submission.status === 'Approved' ||
      submission.status === 'Changes Requested'
  )

  return (
    <div>

      {/* Header */}
      <div className="mb-8">

        <h1 className="text-2xl font-semibold">
          History
        </h1>

        <p className="mt-1 text-sm text-slate-400">
          A record of content reviews and governance decisions.
        </p>

      </div>


      {/* Summary */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">

        <div className="glass rounded-2xl p-5">
          <p className="text-sm text-slate-500">
            Total Decisions
          </p>

          <p className="mt-2 text-2xl font-semibold">
            {historySubmissions.length}
          </p>
        </div>


        <div className="glass rounded-2xl p-5">
          <p className="text-sm text-slate-500">
            Approved
          </p>

          <p className="mt-2 text-2xl font-semibold text-emerald-400">
            {
              historySubmissions.filter(
                (submission) => submission.status === 'Approved'
              ).length
            }
          </p>
        </div>


        <div className="glass rounded-2xl p-5">
          <p className="text-sm text-slate-500">
            Changes Requested
          </p>

          <p className="mt-2 text-2xl font-semibold text-red-400">
            {
              historySubmissions.filter(
                (submission) =>
                  submission.status === 'Changes Requested'
              ).length
            }
          </p>
        </div>

      </div>


      {/* Empty State */}
      {historySubmissions.length === 0 && (
        <div className="flex min-h-[400px] items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-900/40">

          <div className="text-center">

            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-slate-800 text-2xl">
              ◷
            </div>

            <h2 className="text-lg font-medium">
              No review history yet
            </h2>

            <p className="mt-2 max-w-sm text-sm text-slate-400">
              Decisions made on submitted content will appear here.
            </p>

          </div>

        </div>
      )}


      {/* History List */}
      {historySubmissions.length > 0 && (
        <div className="space-y-3">

          {historySubmissions
            .slice()
            .reverse()
            .map((submission) => (

              <div
                key={submission.id}
                className="glass rounded-2xl p-5"
              >

                <div className="flex items-start justify-between gap-6">

                  <div className="flex items-start gap-4">

                    {/* Status Icon */}
                    <div
                      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                        submission.status === 'Approved'
                          ? 'bg-emerald-500/10 text-emerald-400'
                          : 'bg-red-500/10 text-red-400'
                      }`}
                    >
                      {submission.status === 'Approved'
                        ? '✓'
                        : '×'}
                    </div>


                    {/* Information */}
                    <div>

                      <div className="flex flex-wrap items-center gap-3">

                        <h2 className="font-semibold">
                          {submission.title}
                        </h2>

                        <span
                          className={`rounded-full px-3 py-1 text-xs font-medium ${
                            submission.status === 'Approved'
                              ? 'bg-emerald-500/10 text-emerald-400'
                              : 'bg-red-500/10 text-red-400'
                          }`}
                        >
                          {submission.status}
                        </span>

                      </div>

                      <p className="mt-1 text-sm text-slate-500">
                        Submitted {submission.submittedAt}
                      </p>

                    </div>

                  </div>


                  {/* Findings */}
                  <div className="text-right">

                    <p className="text-xs text-slate-500">
                      Findings
                    </p>

                    <p className="mt-1 font-semibold">
                      {submission.findings.length}
                    </p>

                  </div>

                </div>


                {/* Content Preview */}
                <div className="mt-4 rounded-lg bg-slate-950/60 p-4">

                  <p className="line-clamp-2 whitespace-pre-wrap text-sm leading-6 text-slate-400">
                    {submission.content}
                  </p>

                </div>

              </div>

            ))}

        </div>
      )}

    </div>
  )
}

export default History