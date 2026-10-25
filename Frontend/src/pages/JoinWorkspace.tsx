import { useState } from 'react'
import { Modal, Pill } from '../ui'
import { FIELD } from '../styles'
import type { DirectoryEntry } from '../appApi'

type Props = {
  directory: DirectoryEntry[]
  pending: { id: number; name: string } | null
  onJoin: (code: string) => Promise<string | null>
  onRequest: (workspaceId: number) => Promise<string | null>
  onCancelRequest: () => void
  onClose: () => void
}

/** Pick the Brand Manager to work with (they approve you), or join straight away with a code. */
export default function JoinWorkspace({ directory, pending, onJoin, onRequest, onCancelRequest, onClose }: Props) {
  const [tab, setTab] = useState<'managers' | 'code'>('code')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)

  const join = async () => {
    const problem = await onJoin(code)
    if (problem) setError(problem)
    else onClose()
  }

  return (
    <Modal title="Join a workspace" onClose={onClose}>
      {pending && (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-sm">
          <span className="text-amber-200">
            Waiting for the Brand Manager of <strong>{pending.name}</strong> to accept you.
          </span>
          <button onClick={onCancelRequest} className="btn-ghost shrink-0 px-3 py-1.5 text-xs text-slate-200">
            Cancel request
          </button>
        </div>
      )}

      <div className="mb-4 flex rounded-xl bg-black/30 p-1" role="tablist">
        {(['code', 'managers'] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => {
              setTab(t)
              setError(null)
            }}
            className={`flex-1 rounded-lg py-2 text-sm font-medium transition ${tab === t ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white'}`}
          >
            {t === 'managers' ? 'Choose a brand' : 'I have a code'}
          </button>
        ))}
      </div>

      {tab === 'managers' ? (
        <div className="max-h-80 space-y-3 overflow-y-auto pr-1">
          {directory.length === 0 && (
            <p className="rounded-xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-500">
              No brands have been created yet.
            </p>
          )}
          {directory.map((m) => {
            const theirs = m.workspaces
            return (
              <div key={m.managerId} className="rounded-xl border border-white/10 bg-black/20 p-4">
                <p className="font-semibold">{m.brand}</p>
                <p className="text-xs text-slate-500">Managed by {m.managerName}</p>
                {theirs.length === 0 ? (
                  <p className="mt-3 text-xs text-slate-500">No workspace yet.</p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {theirs.map((w) => {
                      const asked = pending?.id === w.id
                      return (
                        <div key={w.id} className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.03] px-3 py-2">
                          <span className="text-sm">{w.name}</span>
                          {asked ? (
                            <Pill tone="warn">Requested</Pill>
                          ) : (
                            <button
                              onClick={async () => setError(await onRequest(w.id))}
                              className="btn-primary px-3 py-1.5 text-xs"
                            >
                              Request to join
                            </button>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ) : (
        <>
          <p className="text-sm leading-6 text-slate-400">Enter the code your Brand Manager gave you.</p>
          <input
            autoFocus
            value={code}
            onChange={(e) => {
              setCode(e.target.value.toUpperCase())
              setError(null)
            }}
            onKeyDown={(e) => e.key === 'Enter' && void join()}
            placeholder="ENG-XXXXXX"
            aria-label="Workspace code"
            className={`${FIELD} mt-4 font-mono tracking-wider`}
          />
        </>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-300">
          {error}
        </p>
      )}

      <div className="mt-6 flex justify-end gap-3">
        <button onClick={onClose} className="btn-ghost px-4 py-2.5 text-sm text-slate-300">
          {tab === 'code' ? 'Cancel' : 'Close'}
        </button>
        {tab === 'code' && (
          <button onClick={() => void join()} className="btn-primary px-5 py-2.5 text-sm">
            Join workspace
          </button>
        )}
      </div>
    </Modal>
  )
}
