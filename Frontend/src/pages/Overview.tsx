import { useMemo, useState } from 'react'
import { BarChart, ColumnChart, PieChart, type Bar } from '../components/Charts'
import { useNameOf } from '../people'
import type { ReviewerAction, ReviewSubmission, Workspace } from '../model'
import { Empty, PageHeader, Pill, Stat } from '../ui'
import { FIELD } from '../styles'

type Props = {
  workspaces: Workspace[]
  submissions: ReviewSubmission[]
  actions: ReviewerAction[]
}

const DAY = 24 * 60 * 60 * 1000

/** Brand Manager home: what creators and reviewers are doing, at a glance. Read-only. */
export default function Overview({ workspaces, submissions, actions }: Props) {
  const nameOf = useNameOf()
  const [scope, setScope] = useState<number | 'all'>('all')

  const view = useMemo(() => {
    const spaces = scope === 'all' ? workspaces : workspaces.filter((w) => w.id === scope)
    const ids = new Set(spaces.map((w) => w.id))
    const subs = submissions.filter((s) => s.workspaceId != null && ids.has(s.workspaceId))
    const acts = actions.filter((a) => a.workspaceId != null && ids.has(a.workspaceId))
    const members = spaces.flatMap((w) => w.members)
    const creators = [...new Set(members.filter((m) => m.role === 'Creator').map((m) => m.userId))]
    const reviewers = [...new Set(members.filter((m) => m.role === 'Reviewer').map((m) => m.userId))]

    const count = (f: (s: ReviewSubmission) => boolean) => subs.filter(f).length
    const byAI = count((s) => s.status === 'Approved' && s.approvedBy === 'AI')
    const byReviewer = count((s) => s.status === 'Approved' && s.approvedBy !== 'AI')
    const pending = count((s) => s.status === 'Pending Review')
    const rejected = count((s) => s.status === 'Changes Requested')

    const perCreator: Bar[] = creators
      .map((id) => ({ label: nameOf(id), value: subs.filter((s) => s.creatorId === id).length }))
      .sort((a, b) => b.value - a.value)

    const perReviewer: Bar[] = reviewers.flatMap((id) => {
      const mine = acts.filter((a) => a.reviewerId === id)
      return [
        { label: `${nameOf(id)} · approved`, value: mine.filter((a) => a.action === 'Direct Approval').length, color: '#34d399' },
        { label: `${nameOf(id)} · rejected`, value: mine.filter((a) => a.action === 'Request Changes').length, color: '#f87171' },
      ]
    })

    const categories = new Map<string, number>()
    for (const s of subs) for (const f of s.findings.filter((x) => x.category !== 'Brand Check')) categories.set(f.category, (categories.get(f.category) ?? 0) + 1)
    const topIssues: Bar[] = [...categories]
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 6)

    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const days: Bar[] = Array.from({ length: 7 }, (_, i) => {
      const start = today.getTime() - (6 - i) * DAY
      return {
        label: new Date(start).toLocaleDateString(undefined, { weekday: 'short' }),
        value: subs.filter((s) => (s.at ?? 0) >= start && (s.at ?? 0) < start + DAY).length,
      }
    })

    const feed = [
      ...subs.map((s) => ({
        at: s.at ?? 0,
        text: `${nameOf(s.creatorId ?? '')} submitted “${s.title}”`,
        tone: 'accent' as const,
      })),
      ...acts.map((a) => ({
        at: a.at ?? 0,
        text: `${nameOf(a.reviewerId ?? '')} ${a.action === 'Direct Approval' ? 'approved' : 'rejected'} “${a.title}”`,
        tone: a.action === 'Direct Approval' ? ('good' as const) : ('bad' as const),
      })),
    ]
      .sort((a, b) => b.at - a.at)
      .slice(0, 8)

    const total = subs.length
    const withFlags = subs.filter((s) => s.findings.some((f) => f.severity !== 'Suggestion')).length
    return { subs, creators, reviewers, byAI, byReviewer, pending, rejected, perCreator, perReviewer, topIssues, days, feed, total, withFlags }
  }, [scope, workspaces, submissions, actions, nameOf])

  if (workspaces.length === 0) {
    return (
      <div className="rise mx-auto max-w-3xl">
        <PageHeader kicker="Brand Manager" title="Overview" />
        <Empty title="Create a workspace to see activity">
          Once creators join your workspace and submit content, you’ll see how it moves through review here.
        </Empty>
      </div>
    )
  }

  const rate = view.total ? Math.round(((view.byAI + view.byReviewer) / view.total) * 100) : 0

  return (
    <div className="rise mx-auto max-w-6xl">
      <PageHeader kicker="Brand Manager" title="Overview" action={
        <select value={scope} onChange={(e) => setScope(e.target.value === 'all' ? 'all' : Number(e.target.value))} aria-label="Workspace" className={`${FIELD} w-auto`}>
          <option value="all">All workspaces</option>
          {workspaces.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
      }>
        What your creators and reviewers are doing. You set the rules; they do the reviewing.
      </PageHeader>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Submissions" value={view.total} />
        <Stat label="Approval rate" value={`${rate}%`} tone="text-emerald-400" />
        <Stat label="Waiting for a reviewer" value={view.pending} tone="text-amber-300" />
        <Stat label="Creators · Reviewers" value={`${view.creators.length} · ${view.reviewers.length}`} />
      </div>

      {view.total === 0 ? (
        <div className="mt-6">
          <Empty title="No submissions yet">Charts appear as soon as a creator sends content for review.</Empty>
        </div>
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <section className="glass rounded-2xl p-6">
            <h2 className="text-lg font-semibold">Where content stands</h2>
            <p className="mt-1 mb-5 text-sm text-slate-400">Every submission by outcome.</p>
            <PieChart
              label="Submissions by outcome"
              slices={[
                { label: 'Cleared by AI', value: view.byAI, color: '#34d399' },
                { label: 'Approved by a reviewer', value: view.byReviewer, color: '#38bdf8' },
                { label: 'Waiting for a reviewer', value: view.pending, color: '#fbbf24' },
                { label: 'Rejected, needs changes', value: view.rejected, color: '#f87171' },
              ]}
            />
          </section>

          <section className="glass rounded-2xl p-6">
            <h2 className="text-lg font-semibold">Submissions, last 7 days</h2>
            <p className="mt-1 mb-5 text-sm text-slate-400">How much content is coming in.</p>
            <ColumnChart label="Submissions per day" bars={view.days} />
          </section>

          <section className="glass rounded-2xl p-6">
            <h2 className="text-lg font-semibold">What creators are sending</h2>
            <p className="mt-1 mb-5 text-sm text-slate-400">Submissions per creator.</p>
            {view.perCreator.length ? <BarChart label="Submissions per creator" bars={view.perCreator} /> : <p className="text-sm text-slate-500">No creators yet.</p>}
          </section>

          <section className="glass rounded-2xl p-6">
            <h2 className="text-lg font-semibold">What reviewers decided</h2>
            <p className="mt-1 mb-5 text-sm text-slate-400">Approvals and rejections per reviewer.</p>
            {view.perReviewer.length ? <BarChart label="Decisions per reviewer" bars={view.perReviewer} /> : <p className="text-sm text-slate-500">No reviewers on this workspace yet.</p>}
          </section>

          <section className="glass rounded-2xl p-6">
            <h2 className="text-lg font-semibold">Most common problems</h2>
            <p className="mt-1 mb-5 text-sm text-slate-400">
              Issues ENGANO flagged, by type. {view.withFlags} of {view.total} drafts had at least one warning.
            </p>
            {view.topIssues.length ? <BarChart label="Findings by category" bars={view.topIssues} color="#a78bfa" /> : <p className="text-sm text-slate-500">Nothing flagged yet.</p>}
          </section>

          <section className="glass rounded-2xl p-6">
            <h2 className="text-lg font-semibold">Recent activity</h2>
            <p className="mt-1 mb-5 text-sm text-slate-400">The latest from your team.</p>
            <ul className="space-y-3">
              {view.feed.map((item, i) => (
                <li key={i} className="flex items-start justify-between gap-3 text-sm">
                  <span className="text-slate-300">{item.text}</span>
                  <Pill tone={item.tone}>{item.at ? new Date(item.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}</Pill>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  )
}
