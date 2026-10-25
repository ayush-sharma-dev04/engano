import { useState, type FormEvent } from 'react'
import { Icon } from '../ui'
import { FIELD } from '../styles'
import ServerAddress from '../components/ServerAddress'
import { auth, type Me } from '../appApi'
import type { Purpose } from '../model'

type Props = { onSignedIn: (token: string, me: Me) => void }

const TYPES: { purpose: Purpose; icon: string; title: string; text: string }[] = [
  { purpose: 'Content Creator', icon: 'pen', title: 'Content creator', text: 'An employee, agency or freelancer (a YouTuber, say) who writes for a brand.' },
  { purpose: 'Business', icon: 'workspace', title: 'Brand manager', text: 'Owns a brand: sets guidelines, adds reviewers, gives final approval.' },
]

/** Sign in or create an account. Accounts live on the ENGANO server, so they work from any device. */
export default function SignIn({ onSignedIn }: Props) {
  const [mode, setMode] = useState<'in' | 'up'>('in')
  const [purpose, setPurpose] = useState<Purpose>('Content Creator')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [brand, setBrand] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const switchMode = (next: 'in' | 'up') => {
    setMode(next)
    setError(null)
  }

  const signUp = async () => {
    if (name.trim().length < 2) return 'Enter your name.'
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return 'Enter a valid email address.'
    if (purpose === 'Business' && brand.trim().length < 2) return 'Give your brand a name.'
    if (password.length < 8) return 'Password must be at least 8 characters.'
    if (password !== confirm) return 'The two passwords do not match.'
    const { token, me } = await auth.signUp({
      name: name.trim(),
      email: email.trim(),
      password,
      purpose,
      brand: purpose === 'Business' ? brand.trim() : undefined,
    })
    onSignedIn(token, me)
    return null
  }

  const signIn = async () => {
    const { token, me } = await auth.signIn(email.trim(), password)
    onSignedIn(token, me)
    return null
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      setError(mode === 'up' ? await signUp() : await signIn())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong. Try again.')
    } finally {
      setBusy(false)
    }
  }

  const up = mode === 'up'

  return (
    <div className="relative min-h-screen text-white">
      <div className="aurora" aria-hidden="true" />
      <div className="relative z-10 flex min-h-screen items-center justify-center px-6 py-10">
        <div className="rise w-full max-w-md">
          <div className="mb-6 flex flex-col items-center text-center">
            <img src="/perry-logo.png" alt="" width={120} className="h-auto drop-shadow-[0_8px_24px_rgba(139,92,246,0.35)]" />
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">ENGANO</h1>
            <p className="mt-2 text-sm text-slate-400">AI-powered brand governance</p>
          </div>

          <form onSubmit={submit} className="glass space-y-5 rounded-2xl p-8">
            <div className="flex rounded-xl bg-black/30 p-1" role="tablist">
              {(['in', 'up'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  role="tab"
                  aria-selected={mode === m}
                  onClick={() => switchMode(m)}
                  className={`flex-1 rounded-lg py-2 text-sm font-medium transition ${
                    mode === m ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {m === 'in' ? 'Sign in' : 'Sign up'}
                </button>
              ))}
            </div>

            {up && (
              <div className="grid gap-3" role="radiogroup" aria-label="Account type">
                {TYPES.map((t) => (
                  <button
                    key={t.purpose}
                    type="button"
                    role="radio"
                    aria-checked={purpose === t.purpose}
                    onClick={() => setPurpose(t.purpose)}
                    className={`flex items-start gap-3 rounded-xl border p-4 text-left transition ${
                      purpose === t.purpose ? 'border-violet-400/70 bg-violet-500/10' : 'border-white/10 hover:bg-white/5'
                    }`}
                  >
                    <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-500/15 text-violet-200">
                      <Icon name={t.icon} />
                    </span>
                    <span>
                      <span className="block text-sm font-semibold">{t.title}</span>
                      <span className="mt-0.5 block text-xs leading-5 text-slate-400">{t.text}</span>
                    </span>
                  </button>
                ))}
              </div>
            )}

            {up && (
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-300">Your name</span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Priya Sharma"
                  autoComplete="name"
                  className={FIELD}
                />
              </label>
            )}

            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-300">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                className={FIELD}
              />
            </label>

            {up && purpose === 'Business' && (
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-300">Create your brand</span>
                <input
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  placeholder="e.g. Nimbus Cloud"
                  className={FIELD}
                />
                <span className="mt-1.5 block text-xs text-slate-500">Creators choose a brand to work with, so use the name they know.</span>
              </label>
            )}

            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-300">Password</span>
              <div className="relative">
                <input
                  type={show ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={up ? 'At least 8 characters' : 'Enter your password'}
                  autoComplete={up ? 'new-password' : 'current-password'}
                  className={`${FIELD} pr-16`}
                />
                <button
                  type="button"
                  onClick={() => setShow((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md px-1 text-xs font-medium text-slate-400 hover:text-white"
                >
                  {show ? 'Hide' : 'Show'}
                </button>
              </div>
            </label>

            {up && (
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-300">Confirm password</span>
                <input
                  type={show ? 'text' : 'password'}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Type it again"
                  autoComplete="new-password"
                  className={FIELD}
                />
              </label>
            )}

            {error && (
              <p role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
                {error}
              </p>
            )}

            <button type="submit" disabled={busy} className="btn-primary w-full px-5 py-3 text-sm">
              {up ? 'Create account' : 'Sign in'}
            </button>

            <p className="text-center text-xs text-slate-500">
              Reviewers don’t sign up: a Brand Manager creates their account.
            </p>
          </form>
          <ServerAddress />
        </div>
      </div>
    </div>
  )
}
