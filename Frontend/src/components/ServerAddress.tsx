import { useEffect, useState } from 'react'
import { apiBase, builtInApi, normalizeApi, proposedApi, resetApi, saveApi } from '../apiUrl'
import { FIELD } from '../styles'

type Status = 'checking' | 'online' | 'offline'

/** Which backend this page talks to, whether it answers, and a way to change it (for a backend behind a changing tunnel). */
export default function ServerAddress() {
  const base = apiBase()
  const suggested = proposedApi()
  const [open, setOpen] = useState(!!suggested)
  const [text, setText] = useState(suggested ?? base)
  const [problem, setProblem] = useState<string | null>(null)
  const [status, setStatus] = useState<Status>('checking')

  useEffect(() => {
    let alive = true
    fetch(`${base}/api/health`, { cache: 'no-store' })
      .then((r) => alive && setStatus(r.ok ? 'online' : 'offline'))
      .catch(() => alive && setStatus('offline'))
    return () => {
      alive = false
    }
  }, [base])

  const apply = (value: string | null) => {
    if (value === null) resetApi()
    else if (!saveApi(value)) return setProblem('Enter a full address such as https://example.trycloudflare.com (http is only allowed for localhost).')
    // Someone signed in to another server is not signed in here.
    try {
      sessionStorage.removeItem('engano_login')
    } catch {
      /* nothing stored */
    }
    location.replace(location.pathname)
  }

  const host = base.replace(/^https?:\/\//, '')
  const tone = status === 'online' ? 'bg-emerald-400' : status === 'offline' ? 'bg-red-400' : 'bg-slate-500'

  return (
    <div className="mt-6 text-center text-xs text-slate-500">
      {suggested && (
        <p role="alert" className="mb-3 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-amber-200">
          This link wants to connect ENGANO to <strong>{suggested.replace(/^https?:\/\//, '')}</strong>. Only continue if you trust whoever sent it:
          your password is sent to that server.
        </p>
      )}
      <p className="flex items-center justify-center gap-2">
        <span className={`h-2 w-2 rounded-full ${tone}`} aria-hidden="true" />
        <span>
          Server: <span className="text-slate-400">{host}</span> ·{' '}
          {status === 'online' ? 'connected' : status === 'offline' ? 'not reachable' : 'checking…'}
        </span>
        <button type="button" onClick={() => setOpen((o) => !o)} className="text-violet-300 underline-offset-2 hover:underline">
          {open ? 'Close' : 'Change'}
        </button>
      </p>
      {status === 'offline' && !open && (
        <p className="mt-2">The backend may be off, or its address changed. Ask whoever runs it for the current address.</p>
      )}
      {open && (
        <div className="mt-3 space-y-2 text-left">
          <input
            value={text}
            onChange={(e) => {
              setText(e.target.value)
              setProblem(null)
            }}
            aria-label="Server address"
            placeholder="https://your-backend.example.com"
            className={FIELD}
          />
          {problem && (
            <p role="alert" className="text-red-300">
              {problem}
            </p>
          )}
          <div className="flex flex-wrap justify-end gap-2">
            {base !== builtInApi && (
              <button type="button" onClick={() => apply(null)} className="btn-ghost px-3 py-1.5 text-slate-300">
                Use the default
              </button>
            )}
            <button type="button" disabled={!normalizeApi(text)} onClick={() => apply(text)} className="btn-primary px-4 py-1.5">
              Use this server
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
