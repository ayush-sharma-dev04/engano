import { useEffect, useRef, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { Icon, Pill } from '../ui'

export type NavItem = { id: string; label: string; icon: string; badge?: number }

type Props = {
  roleLabel: string
  userName: string
  nav: NavItem[]
  headerExtra?: ReactNode
  sidebarNote?: ReactNode
  /** A page that stays mounted (so a draft survives while you look elsewhere) and shows only on `persistentPath`. */
  persistent?: ReactNode
  persistentPath?: string
  /** Shown above the page, e.g. an error banner. */
  notice?: ReactNode
}

/**
 * The frame every signed-in screen shares. The top bar and sidebar are fixed in place: only the
 * page itself scrolls. Each page renders through the router's <Outlet />.
 */
export default function Shell({ roleLabel, userName, nav, headerExtra, sidebarNote, persistent, persistentPath, notice }: Props) {
  const [open, setOpen] = useState(true)
  const { pathname } = useLocation()
  const scroller = useRef<HTMLElement>(null)

  // Each page starts at the top.
  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 })
  }, [pathname])

  const onPersistent = persistentPath !== undefined && pathname === persistentPath

  return (
    <div className="relative flex h-screen flex-col overflow-hidden text-white">
      <div className="aurora" aria-hidden="true" />

      <header className="relative z-20 flex h-16 shrink-0 items-center justify-between border-b border-white/5 bg-slate-950/70 px-5 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setOpen((o) => !o)}
            aria-label={open ? 'Hide sidebar' : 'Show sidebar'}
            className="btn-ghost flex h-9 w-9 items-center justify-center"
          >
            <Icon name="panel" />
          </button>
          <span className="text-lg font-semibold tracking-tight">ENGANO</span>
          <Pill tone="accent">{roleLabel}</Pill>
        </div>

        <div className="flex items-center gap-3">
          {headerExtra}
          <span className="hidden text-sm text-slate-400 sm:inline">{userName}</span>
          <div
            className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-violet-500/40 to-fuchsia-500/30 text-sm font-semibold ring-1 ring-white/10"
            aria-hidden="true"
          >
            {userName.trim().charAt(0).toUpperCase() || 'U'}
          </div>
        </div>
      </header>

      <div className="relative z-10 flex min-h-0 flex-1">
        <aside
          className={`shrink-0 overflow-y-auto overflow-x-hidden border-white/5 bg-slate-950/50 backdrop-blur-xl transition-all duration-300 ${
            open ? 'w-72 border-r p-5' : 'w-0 border-r-0 p-0'
          }`}
        >
          <div className="w-62">
            <p className="mb-4 px-3 text-xs font-semibold uppercase tracking-widest text-slate-500">{roleLabel} workspace</p>

            <nav className="space-y-1.5" aria-label="Main">
              {nav.map((item) => (
                <NavLink
                  key={item.id}
                  to={`/${item.id}`}
                  className={({ isActive }) =>
                    `flex w-full items-center justify-between rounded-xl px-4 py-3.5 text-left text-base font-medium transition-colors ${
                      isActive ? 'bg-white/10 text-white ring-1 ring-white/10' : 'text-slate-400 hover:bg-white/5 hover:text-white'
                    }`
                  }
                >
                  <span className="flex items-center gap-3.5">
                    <Icon name={item.icon} />
                    {item.label}
                  </span>
                  {!!item.badge && (
                    <span className="rounded-full bg-violet-500 px-2 py-0.5 text-xs font-bold text-white">{item.badge}</span>
                  )}
                </NavLink>
              ))}
            </nav>

            {sidebarNote}
          </div>
        </aside>

        <main ref={scroller} className="min-w-0 flex-1 overflow-y-auto p-8">
          {notice}
          <Outlet />
          {persistent && <div className={onPersistent ? '' : 'hidden'}>{persistent}</div>}
        </main>
      </div>
    </div>
  )
}
