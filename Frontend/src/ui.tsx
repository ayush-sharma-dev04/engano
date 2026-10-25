import { useState, type ReactNode } from 'react'

// Small presentational helpers (no app logic).

const PATHS: Record<string, string> = {
  studio: 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z',
  queue: 'M4 6h16M4 12h16M4 18h10',
  approvals: 'M5 12.5l4.5 4.5L19 7.5',
  history: 'M12 7v5l3 2M4 12a8 8 0 1 0 2.3-5.7M4 5v4h4',
  insights: 'M5 19V11M12 19V5M19 19v-6',
  guidelines: 'M6 4h9l3 3v13H6V4zM9 12h6M9 16h6',
  panel: 'M4 5h16v14H4V5zM9 5v14',
  lock: 'M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6v-9z',
  copy: 'M9 9h10v11H9V9zM5 15V4h10',
  refresh: 'M20 12a8 8 0 1 1-2.5-5.8M20 4v5h-5',
  send: 'M12 19V5M6 11l6-6 6 6',
  plus: 'M12 5v14M5 12h14',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  image: 'M4 5h16v14H4V5zM4 16l5-5 4 4 3-3 4 4M9 9.5h.01',
  workspace: 'M4 20V9l8-5 8 5v11M9 20v-6h6v6',
  settings: 'M4 7h10M18 7h2M4 17h2M10 17h10M14 5v4M8 15v4',
  assignments: 'M8 4h8l3 3v13H5V4h3M9 12h6M9 16h4',
  pen: 'M4 20l4-1 11-11-3-3L5 16l-1 4zM14 7l3 3',
  logout: 'M10 5H5v14h5M15 8l4 4-4 4M9 12h10',
  users: 'M16 19v-1a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v1M10 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6M20 19v-1a3 3 0 0 0-2-2.8M16 5.2a3 3 0 0 1 0 5.6',
  globe: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z',
}

export function Icon({ name, className = 'h-5 w-5' }: { name: keyof typeof PATHS | string; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}

/**
 * ENGANO's assistant. While `thinking` it plays the looping thinking animation (transparent
 * WebM); otherwise it shows a still frame. Browsers that can't play VP9-with-alpha fall back
 * to the still frame too.
 */
export function Mascot({ thinking = false, width = 104 }: { thinking?: boolean; width?: number }) {
  const [videoFailed, setVideoFailed] = useState(false)
  const height = Math.round((width * 432) / 544)
  return (
    <div className="shrink-0" style={{ width, height }}>
      {thinking && !videoFailed ? (
        <video
          src="/perry-thinking.webm"
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          width={width}
          height={height}
          onError={() => setVideoFailed(true)}
          aria-hidden="true"
        />
      ) : (
        <img src="/perry-still.png" width={width} height={height} alt="" aria-hidden="true" />
      )}
    </div>
  )
}

/** Page title block used at the top of every dashboard page. */
export function PageHeader({ kicker, title, children, action }: { kicker?: string; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        {kicker && <p className="text-sm font-medium text-violet-300">{kicker}</p>}
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{title}</h1>
        {children && <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{children}</p>}
      </div>
      {action}
    </div>
  )
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-white/10 p-12 text-center">
      <p className="text-lg font-medium">{title}</p>
      {children && <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

const PILL = {
  neutral: 'bg-white/5 text-slate-300',
  good: 'bg-emerald-500/10 text-emerald-300',
  warn: 'bg-amber-400/10 text-amber-300',
  bad: 'bg-red-500/10 text-red-300',
  info: 'bg-sky-400/10 text-sky-300',
  accent: 'bg-violet-500/15 text-violet-200',
} as const

export function Pill({ tone = 'neutral', children }: { tone?: keyof typeof PILL; children: ReactNode }) {
  return <span className={`rounded-full px-3 py-1 text-xs font-medium ${PILL[tone]}`}>{children}</span>
}

export function Stat({ label, value, tone = 'text-white' }: { label: string; value: ReactNode; tone?: string }) {
  return (
    <div className="glass rounded-2xl p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`mt-3 text-3xl font-semibold ${tone}`}>{value}</p>
    </div>
  )
}

/** Centered dialog over a dimmed page. */
export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={title}>
      <div className="glass w-full max-w-lg rounded-2xl border border-white/10 bg-slate-900/90 p-6 shadow-2xl">
        <div className="mb-5 flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="btn-ghost px-2 py-1 text-slate-400">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
