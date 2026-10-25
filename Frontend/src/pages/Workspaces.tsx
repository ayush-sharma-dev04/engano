import { useState } from 'react'
import type { Assignment, Workspace } from '../model'
import { useNameOf } from '../people'
import { Empty, Modal, PageHeader, Pill } from '../ui'
import { FIELD } from '../styles'

type Props = {
  workspaces: Workspace[]
  active: Workspace | null
  assignments: Assignment[]
  onOpen: (id: number) => void
  onCreate: (name: string) => void
  onDelete: (id: number) => void
  onAnswerRequest: (workspaceId: number, requestId: number, accept: boolean) => void
  onCreateReviewer: (workspaceId: number, details: { name: string; email: string }) => Promise<{ error: string } | { password: string }>
  reviewerAccounts: { id: string; name: string; email: string }[]
  onAddReviewer: (workspaceId: number, reviewerId: string) => void
  onUpdateAssignment: (id: number, fields: { title: string; description: string; dueDate: string }) => void
  onDeleteAssignment: (id: number) => void
  onRemoveMember: (workspaceId: number, memberId: number) => void
  onCreateAssignment: (workspaceId: number, title: string, description: string, dueDate: string) => void
}

/** Brand Manager home: every workspace you run, its join code, team and assignments. */
export default function Workspaces({
  workspaces,
  active,
  assignments,
  onOpen,
  onCreate,
  onDelete,
  onAnswerRequest,
  onCreateReviewer,
  onRemoveMember,
  reviewerAccounts,
  onAddReviewer,
  onUpdateAssignment,
  onDeleteAssignment,
  onCreateAssignment,
}: Props) {
  const nameOf = useNameOf()
  const [name, setName] = useState('')
  const [rName, setRName] = useState('')
  const [rEmail, setREmail] = useState('')
  const [existing, setExisting] = useState('')
  const [editing, setEditing] = useState<number | null>(null)
  const [eTitle, setETitle] = useState('')
  const [eDesc, setEDesc] = useState('')
  const [eDue, setEDue] = useState('')
  const [dropping, setDropping] = useState<Assignment | null>(null)
  const [rError, setRError] = useState<string | null>(null)
  const [rMade, setRMade] = useState<{ email: string; password: string } | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [due, setDue] = useState('')
  const [message, setMessage] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [copied, setCopied] = useState(false)

  const create = () => {
    if (!name.trim()) {
      setMessage('Enter a workspace name first.')
      return
    }
    onCreate(name)
    setName('')
    setMessage('Workspace created. Share its code with your creators.')
  }

  const publish = () => {
    if (!active || !title.trim() || !due) {
      setMessage('Enter an assignment title and a due date first.')
      return
    }
    onCreateAssignment(active.id, title, description, due)
    setTitle('')
    setDescription('')
    setDue('')
    setMessage('Assignment published for this workspace.')
  }

  const addReviewer = async () => {
    if (!active) return
    setRError(null)
    setRMade(null)
    const result = await onCreateReviewer(active.id, { name: rName, email: rEmail })
    if ('error' in result) return setRError(result.error)
    setRMade({ email: rEmail.trim(), password: result.password })
    setRName('')
    setREmail('')
  }

  const startEdit = (a: Assignment) => {
    setEditing(a.id)
    setETitle(a.title)
    setEDesc(a.description)
    setEDue(a.dueDate)
  }

  const saveEdit = () => {
    if (editing === null || !eTitle.trim() || !eDue) return
    onUpdateAssignment(editing, { title: eTitle, description: eDesc, dueDate: eDue })
    setEditing(null)
    setMessage('Assignment updated. Creators see the change right away.')
  }

  const copyCode = async () => {
    if (!active) return
    try {
      await navigator.clipboard.writeText(active.code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard blocked */
    }
  }

  const mine = active ? assignments.filter((a) => a.workspaceId === active.id) : []

  return (
    <div className="rise mx-auto max-w-6xl">
      <PageHeader kicker="Brand Manager" title="Workspaces">
        Run a workspace per team. Each has its own join code, creators, reviewers, guidelines and assignments.
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.15fr]">
        <section className="glass rounded-2xl p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Your workspaces</h2>
              <p className="mt-1 text-sm text-slate-400">Pick one to manage it.</p>
            </div>
            <Pill>{workspaces.length} total</Pill>
          </div>

          <div className="mt-5 space-y-3">
            {workspaces.length === 0 ? (
              <Empty title="No workspaces yet">Create your first one below.</Empty>
            ) : (
              workspaces.map((w) => (
                <button
                  key={w.id}
                  onClick={() => onOpen(w.id)}
                  className={`w-full rounded-xl border p-4 text-left transition ${
                    active?.id === w.id ? 'border-violet-400/60 bg-violet-500/10' : 'border-white/10 bg-black/20 hover:border-white/20'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-semibold">{w.name}</p>
                      <p className="mt-1 font-mono text-xs text-violet-300">{w.code}</p>
                    </div>
                    <div className="flex gap-2">
                      {(w.requests?.length ?? 0) > 0 && <Pill tone="warn">{w.requests?.length} request{w.requests?.length === 1 ? '' : 's'}</Pill>}
                      <Pill>
                        {w.members.length} member{w.members.length === 1 ? '' : 's'}
                      </Pill>
                    </div>
                  </div>
                  <p className="mt-3 text-xs text-slate-500">Created {w.createdAt}</p>
                </button>
              ))
            )}
          </div>

          <div className="mt-6 border-t border-white/5 pt-6">
            <h3 className="font-semibold">Create a workspace</h3>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && create()}
              placeholder="e.g. Nimbus Marketing Team"
              className={`${FIELD} mt-3`}
            />
            <button onClick={create} className="btn-primary mt-3 px-5 py-2.5 text-sm">
              Create workspace
            </button>
          </div>
        </section>

        <section className="space-y-6">
          {!active ? (
            <Empty title="Select a workspace">Choose one on the left to manage its team and assignments.</Empty>
          ) : (
            <>
              <div className="glass rounded-2xl p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-violet-300">Active workspace</p>
                    <h2 className="mt-2 text-2xl font-semibold">{active.name}</h2>
                    <p className="mt-1 font-mono text-sm text-slate-400">Join code: {active.code}</p>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={copyCode} className="btn-ghost px-3 py-2 text-xs text-slate-300">
                      {copied ? 'Copied' : 'Copy code'}
                    </button>
                    <button
                      onClick={() => setConfirmDelete(true)}
                      className="rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs font-semibold text-red-400 hover:bg-red-500/10"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>

              {(active.requests?.length ?? 0) > 0 && (
                <div className="glass rounded-2xl border border-amber-400/30 p-6">
                  <h2 className="text-lg font-semibold">Join requests</h2>
                  <p className="mt-1 text-sm text-slate-400">Creators who chose you and are waiting for an answer.</p>
                  <div className="mt-5 space-y-3">
                    {active.requests?.map((r) => (
                      <div key={r.id} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 p-4">
                        <p className="text-sm font-medium">{nameOf(r.userId)}</p>
                        <div className="flex gap-2">
                          <button onClick={() => onAnswerRequest(active.id, r.id, false)} className="btn-ghost px-3 py-1.5 text-xs text-slate-300">
                            Decline
                          </button>
                          <button onClick={() => onAnswerRequest(active.id, r.id, true)} className="btn-primary px-3 py-1.5 text-xs">
                            Accept
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="glass rounded-2xl p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-semibold">Team</h2>
                    <p className="mt-1 text-sm text-slate-400">People who joined with the code.</p>
                  </div>
                  <Pill>
                    {active.members.length} member{active.members.length === 1 ? '' : 's'}
                  </Pill>
                </div>

                <div className="mt-5 space-y-3">
                  {active.members.length === 0 ? (
                    <p className="rounded-xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-500">
                      No one has joined yet. Share {active.code}.
                    </p>
                  ) : (
                    active.members.map((m) => (
                      <div key={m.id} className="flex items-center justify-between rounded-xl border border-white/10 bg-black/20 p-4">
                        <p className="text-sm font-medium">{nameOf(m.userId)}</p>
                        <div className="flex items-center gap-3">
                          <Pill tone={m.role === 'Reviewer' ? 'warn' : 'accent'}>{m.role}</Pill>
                          <button
                            onClick={() => onRemoveMember(active.id, m.id)}
                            aria-label={`Remove ${nameOf(m.userId)}`}
                            className="text-xs text-slate-500 hover:text-red-300"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                <div className="mt-5 border-t border-white/5 pt-5">
                  {(() => {
                    const spare = reviewerAccounts.filter((a) => !active.members.some((m) => m.userId === a.id))
                    return spare.length > 0 ? (
                      <div className="mb-6 flex flex-col gap-3 sm:flex-row">
                        <select
                          value={existing}
                          onChange={(e) => setExisting(e.target.value)}
                          aria-label="Existing reviewer"
                          className={`${FIELD} flex-1`}
                        >
                          <option value="">Add one of your reviewers to this workspace</option>
                          {spare.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.name} · {a.email}
                            </option>
                          ))}
                        </select>
                        <button
                          disabled={!existing}
                          onClick={() => {
                            onAddReviewer(active.id, existing)
                            setExisting('')
                          }}
                          className="btn-primary px-5 py-3 text-sm"
                        >
                          Add reviewer
                        </button>
                      </div>
                    ) : null
                  })()}
                  <h3 className="font-semibold">Create a new reviewer</h3>
                  <p className="mt-1 text-sm text-slate-400">
                    Reviewers are created by you, not by sign-up. ENGANO makes a password for them. Removing a reviewer only takes them off
                    this workspace.
                  </p>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <input value={rName} onChange={(e) => setRName(e.target.value)} placeholder="Reviewer’s name" className={FIELD} />
                    <input value={rEmail} onChange={(e) => setREmail(e.target.value)} placeholder="reviewer@company.com" type="email" className={FIELD} />
                  </div>
                  <button onClick={addReviewer} className="btn-primary mt-3 px-5 py-2.5 text-sm">
                    Create reviewer account
                  </button>
                  {rError && (
                    <p role="alert" className="mt-3 text-sm text-red-300">
                      {rError}
                    </p>
                  )}
                  {rMade && (
                    <div role="status" className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-100">
                      <p className="font-semibold">Reviewer created. Send them these sign-in details; the password is shown only now.</p>
                      <p className="mt-2 font-mono">Email: {rMade.email}</p>
                      <p className="font-mono">Password: {rMade.password}</p>
                      <button
                        onClick={() => navigator.clipboard?.writeText(`Email: ${rMade.email}\nPassword: ${rMade.password}`)}
                        className="btn-ghost mt-3 px-3 py-1.5 text-xs text-emerald-100"
                      >
                        Copy details
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <div className="glass rounded-2xl p-6">
                <h2 className="text-lg font-semibold">New assignment</h2>
                <p className="mt-1 text-sm text-slate-400">Give creators a topic and a deadline.</p>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Assignment title, e.g. Launch announcement"
                  className={`${FIELD} mt-5`}
                />
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What should creators write? Platform, tone, key points…"
                  className={`${FIELD} mt-3 resize-none leading-6`}
                />
                <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
                  <label className="flex-1">
                    <span className="block text-sm font-medium text-slate-300">Last day to submit</span>
                    <input type="date" value={due} onChange={(e) => setDue(e.target.value)} className={`${FIELD} mt-2`} />
                  </label>
                  <button onClick={publish} className="btn-primary px-5 py-3 text-sm">
                    Publish assignment
                  </button>
                </div>
                {message && (
                  <p role="status" className="mt-4 text-sm text-violet-200">
                    {message}
                  </p>
                )}
              </div>

              <div className="glass rounded-2xl p-6">
                <h2 className="text-lg font-semibold">Assignments</h2>
                <div className="mt-5 space-y-3">
                  {mine.length === 0 ? (
                    <p className="rounded-xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-500">
                      Nothing published for this workspace yet.
                    </p>
                  ) : (
                    mine.map((a) =>
                      editing === a.id ? (
                        <div key={a.id} className="rounded-xl border border-violet-400/40 bg-black/20 p-5">
                          <input value={eTitle} onChange={(e) => setETitle(e.target.value)} aria-label="Assignment title" className={FIELD} />
                          <textarea
                            rows={3}
                            value={eDesc}
                            onChange={(e) => setEDesc(e.target.value)}
                            aria-label="Assignment details"
                            className={`${FIELD} mt-3 resize-none leading-6`}
                          />
                          <input type="date" value={eDue} onChange={(e) => setEDue(e.target.value)} aria-label="Due date" className={`${FIELD} mt-3`} />
                          <div className="mt-4 flex justify-end gap-3">
                            <button onClick={() => setEditing(null)} className="btn-ghost px-4 py-2 text-sm text-slate-300">
                              Cancel
                            </button>
                            <button onClick={saveEdit} disabled={!eTitle.trim() || !eDue} className="btn-primary px-4 py-2 text-sm">
                              Save changes
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div key={a.id} className="rounded-xl border border-white/10 bg-black/20 p-5">
                          <div className="flex flex-wrap items-start justify-between gap-4">
                            <div>
                              <h3 className="font-semibold">{a.title}</h3>
                              {a.description && <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-400">{a.description}</p>}
                            </div>
                            <Pill tone="warn">Due {a.dueDate}</Pill>
                          </div>
                          <div className="mt-4 flex items-center justify-between">
                            <p className="text-xs text-slate-600">Published {a.createdAt}</p>
                            <div className="flex gap-2">
                              <button onClick={() => startEdit(a)} className="btn-ghost px-3 py-1.5 text-xs text-slate-300">
                                Edit
                              </button>
                              <button onClick={() => setDropping(a)} className="btn-ghost px-3 py-1.5 text-xs text-red-300">
                                Delete
                              </button>
                            </div>
                          </div>
                        </div>
                      )
                    )
                  )}
                </div>
              </div>
            </>
          )}
        </section>
      </div>

      {dropping && (
        <Modal title={`Delete “${dropping.title}”?`} onClose={() => setDropping(null)}>
          <p className="text-sm leading-6 text-slate-400">Creators will no longer see this assignment. Drafts already written stay.</p>
          <div className="mt-6 flex justify-end gap-3">
            <button onClick={() => setDropping(null)} className="btn-ghost px-4 py-2.5 text-sm text-slate-300">
              Cancel
            </button>
            <button
              onClick={() => {
                onDeleteAssignment(dropping.id)
                setDropping(null)
              }}
              className="rounded-lg bg-red-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-400"
            >
              Delete assignment
            </button>
          </div>
        </Modal>
      )}

      {confirmDelete && active && (
        <Modal title={`Delete “${active.name}”?`} onClose={() => setConfirmDelete(false)}>
          <p className="text-sm leading-6 text-slate-400">
            Its assignments, guidelines and submissions are removed too. Members lose access. This cannot be undone.
          </p>
          <div className="mt-6 flex justify-end gap-3">
            <button onClick={() => setConfirmDelete(false)} className="btn-ghost px-4 py-2.5 text-sm text-slate-300">
              Cancel
            </button>
            <button
              onClick={() => {
                onDelete(active.id)
                setConfirmDelete(false)
              }}
              className="rounded-lg bg-red-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-400"
            >
              Delete workspace
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
