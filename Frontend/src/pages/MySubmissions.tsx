import { useState } from 'react'
import type { ReviewSubmission } from '../model'
import { Empty, PageHeader, Pill } from '../ui'

const FILTERS = ['All', 'Request Changes', 'Approved'] as const
type Filter = (typeof FILTERS)[number]

type Props = {
  submissions: ReviewSubmission[]
  onEdit: (submission: ReviewSubmission) => void
}

/** Joined creator: what was approved, what needs changes, and what is still waiting. */
export default function MySubmissions({ submissions, onEdit }: Props) {
  const [filter, setFilter] = useState<Filter>('All')

  const shown = submissions.filter(
    (s) =>
      filter === 'All' ||
      (filter === 'Request Changes' && s.status === 'Changes Requested') ||
      (filter === 'Approved' && s.status === 'Approved')
  )

  return (
    <div className="rise mx-auto max-w-5xl">
      <PageHeader kicker="My submissions" title="Approvals">
        See which drafts were approved and which need changes.
      </PageHeader>

      <div className="mb-6 flex flex-wrap gap-2" role="radiogroup" aria-label="Filter submissions">
        {FILTERS.map((f) => (
          <button
            key={f}
            role="radio"
            aria-checked={filter === f}
            onClick={() => setFilter(f)}
            className={`rounded-full px-4 py-1.5 text-sm transition ${
              filter === f ? 'bg-violet-500 text-white' : 'border border-white/10 text-slate-300 hover:bg-white/5'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <Empty title="No matching submissions">Your reviewed content will appear here.</Empty>
      ) : (
        <div className="space-y-4">
          {shown.map((s) => (
            <div key={s.id} className="glass rounded-2xl p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold">{s.title}</h2>
                  <p className="mt-1 text-xs text-slate-500">Submitted {s.submittedAt}</p>
                </div>
                <div className="flex gap-2">
                  {s.approvedBy && <Pill tone="info">Cleared by {s.approvedBy}</Pill>}
                  {s.published && <Pill tone="accent">Published</Pill>}
                  <Pill tone={s.status === 'Approved' ? 'good' : s.status === 'Changes Requested' ? 'bad' : 'warn'}>{s.status}</Pill>
                </div>
              </div>
              <p className="mt-5 whitespace-pre-wrap rounded-xl bg-black/30 p-5 text-sm leading-7 text-slate-300">{s.content}</p>
              {s.status === 'Changes Requested' && (
                <div className="mt-5 rounded-xl border border-red-500/20 bg-red-500/5 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wider text-red-300">Reviewer feedback</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">{s.reviewerComment || 'Changes were requested.'}</p>
                  <button onClick={() => onEdit(s)} className="btn-primary mt-4 px-5 py-2.5 text-sm">
                    Edit &amp; resubmit
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
