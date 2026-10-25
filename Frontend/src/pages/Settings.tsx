import { useState } from 'react'
import type { Role, Workspace } from '../model'
import { Icon, PageHeader, Pill } from '../ui'
import { FIELD } from '../styles'

type Props = {
  name: string
  email: string
  role: Role
  workspace: Workspace | null
  canLeave: boolean
  /** Reviewers only: where to send review requests. */
  contact?: { whatsapp: string; discordId: string }
  onSaveContact?: (whatsapp: string, discordId: string) => Promise<string | null>
  onTestContact?: () => Promise<Record<string, string> | string>
  onLeave: () => void
  onLogout: () => void
}

/** Where a reviewer is told that a draft is waiting. Saved on the server, so it follows them to any device. */
function ReviewMessages({ contact, onSave, onTest }: { contact: { whatsapp: string; discordId: string }; onSave: (w: string, d: string) => Promise<string | null>; onTest: () => Promise<Record<string, string> | string> }) {
  // What the person typed, until it is saved; then the server's (tidied) copy is shown again.
  const [draft, setDraft] = useState<{ w?: string; d?: string }>({})
  const whatsapp = draft.w ?? contact.whatsapp
  const discord = draft.d ?? contact.discordId
  const setWhatsapp = (w: string) => setDraft((x) => ({ ...x, w }))
  const setDiscord = (d: string) => setDraft((x) => ({ ...x, d }))
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null)
  const [results, setResults] = useState<Record<string, string> | null>(null)
  const [busy, setBusy] = useState(false)
  const saved = draft.w === undefined && draft.d === undefined

  const save = async () => {
    setBusy(true)
    setResults(null)
    const problem = await onSave(whatsapp, discord)
    if (!problem) setDraft({})
    setNote(problem ? { ok: false, text: problem } : { ok: true, text: 'Saved. New review requests will be sent there.' })
    setBusy(false)
  }

  const test = async () => {
    setBusy(true)
    setNote(null)
    const out = await onTest()
    if (typeof out === 'string') setNote({ ok: false, text: out })
    else setResults(out)
    setBusy(false)
  }

  return (
    <section className="glass mt-6 rounded-2xl p-6">
      <h2 className="text-lg font-semibold">Review messages</h2>
      <p className="mt-1 text-sm text-slate-400">
        Add where you want to be told when a draft needs you. Each one is optional. You always see the queue in ENGANO too.
      </p>

      <label className="mt-6 block">
        <span className="mb-2 block text-sm font-medium text-slate-300">WhatsApp number</span>
        <input
          value={whatsapp}
          onChange={(e) => setWhatsapp(e.target.value)}
          placeholder="Country code first, e.g. 919876543210"
          inputMode="tel"
          className={FIELD}
        />
      </label>

      <label className="mt-5 block">
        <span className="mb-2 block text-sm font-medium text-slate-300">Discord user ID</span>
        <input
          value={discord}
          onChange={(e) => setDiscord(e.target.value)}
          placeholder="17 to 19 digits, e.g. 123456789012345678"
          inputMode="numeric"
          className={FIELD}
        />
        <span className="mt-1.5 block text-xs text-slate-500">
          In Discord turn on Settings → Advanced → Developer Mode, then right-click your name and choose Copy User ID. You must share a server with the
          ENGANO bot.
        </span>
      </label>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button onClick={save} disabled={busy || saved} className="btn-primary px-5 py-2.5 text-sm">
          Save
        </button>
        <button
          onClick={test}
          disabled={busy || !saved || (!contact.whatsapp && !contact.discordId)}
          className="btn-ghost px-5 py-2.5 text-sm text-slate-300"
        >
          Send a test message
        </button>
      </div>

      {note && (
        <p role={note.ok ? 'status' : 'alert'} className={`mt-4 text-sm ${note.ok ? 'text-emerald-300' : 'text-red-300'}`}>
          {note.text}
        </p>
      )}
      {results && (
        <ul className="mt-4 space-y-2 text-sm">
          {Object.entries(results).map(([platform, result]) => (
            <li key={platform} className="flex items-start gap-3">
              <Pill tone={result === 'sent' ? 'good' : 'bad'}>{platform}</Pill>
              <span className={result === 'sent' ? 'text-emerald-300' : 'text-red-300'}>{result === 'sent' ? 'Test message sent.' : result}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-5 text-xs leading-5 text-slate-500">
        WhatsApp only delivers to people who have messaged the ENGANO number in the last 24 hours (and, while it is a Meta test number, to numbers
        added to its allowed list). The test message tells you straight away if yours can receive.
      </p>
    </section>
  )
}

export default function Settings(props: Props) {
  return (
    <div className="rise max-w-3xl">
      <PageHeader title="Settings">Your profile.</PageHeader>

      <section className="glass rounded-2xl p-6">
        <h2 className="text-lg font-semibold">Profile</h2>
        <dl className="mt-6 space-y-5 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">Name</dt>
            <dd className="mt-2 text-slate-200">{props.name}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">Email</dt>
            <dd className="mt-2 text-slate-200">{props.email}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">Role</dt>
            <dd className="mt-2 text-violet-300">{props.role}</dd>
          </div>
          {props.workspace && (
            <div>
              <dt className="text-xs uppercase tracking-wider text-slate-500">Workspace</dt>
              <dd className="mt-2 text-slate-200">{props.workspace.name}</dd>
            </div>
          )}
        </dl>
        <div className="mt-8 flex flex-wrap gap-3">
          {props.canLeave && (
            <button
              onClick={props.onLeave}
              className="rounded-lg border border-red-500/30 bg-red-500/5 px-5 py-2.5 text-sm font-semibold text-red-400 hover:bg-red-500/10"
            >
              Leave workspace
            </button>
          )}
          <button onClick={props.onLogout} className="btn-ghost flex items-center gap-2 px-5 py-2.5 text-sm text-slate-300">
            <Icon name="logout" className="h-4 w-4" />
            Log out
          </button>
        </div>
      </section>

      {props.contact && props.onSaveContact && props.onTestContact && (
        <ReviewMessages contact={props.contact} onSave={props.onSaveContact} onTest={props.onTestContact} />
      )}
    </div>
  )
}
