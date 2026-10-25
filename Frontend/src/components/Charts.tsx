// Small dependency-free SVG charts. Colours always come with a text label and a number, so
// nothing relies on colour alone.

export type Slice = { label: string; value: number; color: string }

export function PieChart({ slices, label }: { slices: Slice[]; label: string }) {
  const total = slices.reduce((sum, s) => sum + s.value, 0)
  const R = 54
  const C = 2 * Math.PI * R
  let offset = 0

  return (
    <div className="flex flex-wrap items-center gap-6">
      <svg viewBox="0 0 140 140" className="h-40 w-40 shrink-0 -rotate-90" role="img" aria-label={label}>
        <circle cx="70" cy="70" r={R} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="22" />
        {total > 0 &&
          slices
            .filter((s) => s.value > 0)
            .map((s) => {
              const length = (s.value / total) * C
              const circle = (
                <circle
                  key={s.label}
                  cx="70"
                  cy="70"
                  r={R}
                  fill="none"
                  stroke={s.color}
                  strokeWidth="22"
                  strokeDasharray={`${length} ${C - length}`}
                  strokeDashoffset={-offset}
                >
                  <title>{`${s.label}: ${s.value}`}</title>
                </circle>
              )
              offset += length
              return circle
            })}
        <text x="70" y="70" textAnchor="middle" dominantBaseline="middle" className="fill-white text-[22px] font-semibold" transform="rotate(90 70 70)">
          {total}
        </text>
      </svg>
      <ul className="space-y-2 text-sm">
        {slices.map((s) => (
          <li key={s.label} className="flex items-center gap-2">
            <span className="h-3 w-3 shrink-0 rounded-sm" style={{ background: s.color }} aria-hidden="true" />
            <span className="text-slate-300">{s.label}</span>
            <span className="ml-auto pl-4 font-medium tabular-nums">{s.value}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export type Bar = { label: string; value: number; color?: string }

export function BarChart({ bars, label, color = '#8b5cf6' }: { bars: Bar[]; label: string; color?: string }) {
  const max = Math.max(1, ...bars.map((b) => b.value))
  return (
    <ul className="space-y-3" aria-label={label}>
      {bars.map((b) => (
        <li key={b.label} className="grid grid-cols-[minmax(0,9rem)_1fr_2rem] items-center gap-3 text-sm">
          <span className="truncate text-slate-300" title={b.label}>
            {b.label}
          </span>
          <span className="h-3 overflow-hidden rounded-full bg-white/5">
            <span
              className="block h-full rounded-full transition-all"
              style={{ width: `${(b.value / max) * 100}%`, background: b.color ?? color }}
            />
          </span>
          <span className="text-right font-medium tabular-nums">{b.value}</span>
        </li>
      ))}
    </ul>
  )
}

/** Vertical columns, e.g. submissions per day. */
export function ColumnChart({ bars, label, color = '#8b5cf6' }: { bars: Bar[]; label: string; color?: string }) {
  const max = Math.max(1, ...bars.map((b) => b.value))
  return (
    <div className="flex h-44 items-end gap-3" role="img" aria-label={label}>
      {bars.map((b) => (
        <div key={b.label} className="flex h-full flex-1 flex-col items-center justify-end gap-2">
          <span className="text-xs font-medium tabular-nums text-slate-300">{b.value}</span>
          <span
            className="w-full max-w-10 rounded-t-md transition-all"
            style={{ height: `${Math.max(2, (b.value / max) * 100)}%`, background: b.color ?? color, opacity: b.value ? 1 : 0.25 }}
          />
          <span className="text-xs text-slate-500">{b.label}</span>
        </div>
      ))}
    </div>
  )
}
