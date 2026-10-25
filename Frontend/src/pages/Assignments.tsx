import type { Assignment, ReviewSubmission, Workspace } from '../model'
import { Empty, PageHeader, Pill } from '../ui'

type Props = {
  workspace: Workspace
  assignments: Assignment[]
  drafts: ReviewSubmission[]
  onStart: (assignment: Assignment) => void
  onNewDraft: () => void
}

const TONE = { Approved: 'good', 'Changes Requested': 'bad', 'Pending Review': 'warn' } as const

/** Joined creator: what the Brand Manager asked for, and where my drafts stand. */
export default function Assignments({ workspace, assignments, drafts, onStart, onNewDraft }: Props) {
  const here = assignments.filter((a) => a.workspaceId === workspace.id)

  return (
    <div className="rise mx-auto max-w-5xl">
      <PageHeader
        kicker={workspace.name}
        title="Assignments"
        action={
          <button onClick={onNewDraft} className="btn-primary px-5 py-2.5 text-sm">
            New draft
          </button>
        }
      >
        Write for the topics your Brand Manager posted. ENGANO reviews each draft before it goes on.
      </PageHeader>

      <section className="glass rounded-2xl p-6">
        <h2 className="text-lg font-semibold">From your Brand Manager</h2>
        <div className="mt-5 space-y-3">
          {here.length === 0 ? (
            <p className="rounded-xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-500">
              No assignments have been posted yet. You can still start a draft of your own.
            </p>
          ) : (
            here.map((a) => (
              <button
                key={a.id}
                onClick={() => onStart(a)}
                className="w-full rounded-xl border border-white/10 bg-black/20 p-5 text-left transition hover:border-violet-400/50"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold">{a.title}</h3>
                    {a.description && <p className="mt-2 text-sm leading-6 text-slate-400">{a.description}</p>}
                  </div>
                  <Pill tone="warn">Due {a.dueDate}</Pill>
                </div>
                <p className="mt-3 text-xs font-medium text-violet-300">Start a draft →</p>
              </button>
            ))
          )}
        </div>
      </section>

      <h2 className="mb-4 mt-10 text-lg font-semibold">My drafts</h2>
      {drafts.length === 0 ? (
        <Empty title="No drafts yet">Pick an assignment above or start a new draft.</Empty>
      ) : (
        <div className="space-y-4">
          {drafts.map((d) => (
            <div key={d.id} className="glass rounded-2xl p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold">{d.title}</h3>
                  <p className="mt-1 text-xs text-slate-500">{d.submittedAt}</p>
                </div>
                <Pill tone={TONE[d.status]}>{d.status}</Pill>
              </div>
              <p className="mt-4 line-clamp-3 whitespace-pre-wrap text-sm leading-6 text-slate-400">{d.content}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
