import type { ReviewerAction } from '../model'
import { Empty, PageHeader, Pill, Stat } from '../ui'

type Props = { userId: string; actions: ReviewerAction[] }

export default function ReviewerHistory({ userId, actions }: Props) {
  const mine = actions.filter((a) => a.reviewerId === userId)
  const approved = mine.filter((a) => a.action === 'Direct Approval').length
  const rejected = mine.filter((a) => a.action === 'Request Changes').length

  return (
    <div className="rise mx-auto max-w-5xl">
      <PageHeader kicker="Reviewer activity" title="Review history">
        Every decision you made in the queue.
      </PageHeader>
      <div className="grid gap-4 md:grid-cols-3">
        <Stat label="Decisions" value={mine.length} />
        <Stat label="Approved" value={approved} tone="text-emerald-400" />
        <Stat label="Rejected" value={rejected} tone="text-red-400" />
      </div>
      <div className="glass mt-6 rounded-2xl p-6">
        <h2 className="text-lg font-semibold">Decisions</h2>
        <div className="mt-5 space-y-3">
          {mine.length === 0 ? (
            <Empty title="No decisions yet">Approve or reject a draft in the Review Queue.</Empty>
          ) : (
            mine.map((a) => (
              <div key={a.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 p-4">
                <div>
                  <p className="text-sm font-medium">{a.title}</p>
                  <p className="mt-1 text-xs text-slate-500">{a.at ? new Date(a.at).toLocaleString() : a.createdAt}</p>
                </div>
                <Pill tone={a.action === 'Request Changes' ? 'bad' : 'good'}>{a.action === 'Request Changes' ? 'Rejected' : 'Approved'}</Pill>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
