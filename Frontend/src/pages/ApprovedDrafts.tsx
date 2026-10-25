import { useState } from 'react'
import { useNameOf } from '../people'
import type { ReviewSubmission, Workspace } from '../model'
import { Empty, PageHeader, Pill } from '../ui'
import { FIELD } from '../styles'

type Props = { workspaces: Workspace[]; submissions: ReviewSubmission[]; onOpen: (submission: ReviewSubmission) => void }

/** Brand Manager: every draft that was approved (by ENGANO or a reviewer), read-only. */
export default function ApprovedDrafts({ workspaces, submissions, onOpen }: Props) {
  const nameOf = useNameOf()
  const [scope, setScope] = useState<number | 'all'>('all')
  const [by, setBy] = useState<'all' | 'AI' | 'Reviewer'>('all')
  const [query, setQuery] = useState('')

  const shown = submissions
    .filter((s) => s.status === 'Approved')
    .filter((s) => scope === 'all' || s.workspaceId === scope)
    .filter((s) => by === 'all' || s.approvedBy === by)
    .filter((s) => {
      const q = query.trim().toLowerCase()
      return !q || `${s.title} ${s.content} ${nameOf(s.creatorId ?? '')}`.toLowerCase().includes(q)
    })
  const total = submissions.filter((s) => s.status === 'Approved').length

  return (
    <div className="rise mx-auto max-w-5xl">
      <PageHeader kicker="Brand Manager" title="Approved drafts">
        Everything your creators wrote that was approved, by ENGANO or by a reviewer. Read-only.
      </PageHeader>

      <div className="mb-6 grid gap-3 sm:grid-cols-[1fr_auto_auto]">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search title, text or creator" aria-label="Search approved drafts" className={FIELD} />
        <select value={scope} onChange={(e) => setScope(e.target.value === 'all' ? 'all' : Number(e.target.value))} aria-label="Workspace" className={`${FIELD} sm:w-auto`}>
          <option value="all">All workspaces</option>
          {workspaces.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
        <select value={by} onChange={(e) => setBy(e.target.value as typeof by)} aria-label="Approved by" className={`${FIELD} sm:w-auto`}>
          <option value="all">Approved by anyone</option>
          <option value="AI">Cleared by ENGANO</option>
          <option value="Reviewer">Approved by a reviewer</option>
        </select>
      </div>

      {shown.length === 0 ? (
        <Empty title={total ? 'Nothing matches' : 'No approved drafts yet'}>
          {total ? 'Try a different search or filter.' : 'Approved drafts from your creators will appear here.'}
        </Empty>
      ) : (
        <div className="space-y-4">
          {shown.map((s) => (
            <article key={s.id} className="glass rounded-2xl p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold">{s.title}</h2>
                  <p className="mt-1 text-xs text-slate-500">
                    By {nameOf(s.creatorId ?? '')} · {s.submittedAt} · {workspaces.find((w) => w.id === s.workspaceId)?.name ?? ''}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Pill tone={s.approvedBy === 'AI' ? 'info' : 'good'}>{s.approvedBy === 'AI' ? 'Cleared by ENGANO' : 'Approved by a reviewer'}</Pill>
                  {s.findings.filter((f) => f.category !== 'Brand Check').length > 0 && (
                    <Pill tone="warn">{s.findings.filter((f) => f.category !== 'Brand Check').length} finding(s) noted</Pill>
                  )}
                </div>
              </div>
              <p className="mt-5 whitespace-pre-wrap rounded-xl bg-black/30 p-5 text-sm leading-7 text-slate-300">{s.content}</p>
              <div className="mt-4">
                <button onClick={() => onOpen(s)} className="btn-ghost px-4 py-2 text-sm text-violet-200">
                  History &amp; comments ({s.version ?? 1} version{(s.version ?? 1) === 1 ? '' : 's'}, {s.comments ?? 0} comment{(s.comments ?? 0) === 1 ? '' : 's'})
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
