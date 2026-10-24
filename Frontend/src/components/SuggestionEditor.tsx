import { useEffect, useMemo, useRef, useState } from 'react'
import type { Finding } from '../App'
import { locate } from '../suggestions'

// Grammarly-style editor: the draft is a normal textarea; problem text is underlined
// by a mirrored layer behind it. Click an underline to see the issue and Apply / Dismiss.

const UNDERLINE: Record<Finding['severity'], string> = {
  Critical: 'decoration-red-400',
  Warning: 'decoration-amber-300',
  Suggestion: 'decoration-sky-400',
}

type Props = {
  value: string
  onChange: (value: string) => void
  findings: Finding[]
  hidden: Set<number>
  onApply: (key: number) => void
  onDismiss: (key: number) => void
  placeholder?: string
  /** No border or background: for use inside a chat bubble or composer. */
  bare?: boolean
  rows?: number
}

export default function SuggestionEditor({ value, onChange, findings, hidden, onApply, onDismiss, placeholder, bare, rows = 12 }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const backRef = useRef<HTMLDivElement>(null)
  const areaRef = useRef<HTMLTextAreaElement>(null)
  const [activeKey, setActiveKey] = useState<number | null>(null)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)

  const located = useMemo(() => locate(value, findings, hidden), [value, findings, hidden])
  const active = located.find((l) => l.key === activeKey) ?? null

  const segments = useMemo(() => {
    const parts: React.ReactNode[] = []
    let cursor = 0
    located.forEach((l) => {
      if (l.start > cursor) parts.push(value.slice(cursor, l.start))
      parts.push(
        <mark
          key={l.key}
          data-key={l.key}
          className={`rounded-sm bg-transparent text-transparent underline decoration-wavy decoration-2 underline-offset-4 ${UNDERLINE[l.finding.severity]} ${
            l.key === activeKey ? 'bg-white/10' : ''
          }`}
        >
          {value.slice(l.start, l.end)}
        </mark>
      )
      cursor = l.end
    })
    parts.push(value.slice(cursor))
    return parts
  }, [located, value, activeKey])

  // Position the card under the underlined phrase. Done in event handlers (not an effect)
  // because the card only ever opens or moves in response to a click, key press or scroll.
  const placeFor = (key: number | null) => {
    const mark =
      key === null ? null : backRef.current?.querySelector<HTMLElement>(`mark[data-key="${key}"]`)
    const wrap = wrapRef.current
    if (!mark || !wrap) return null
    const scroll = areaRef.current?.scrollTop ?? 0
    return {
      top: mark.offsetTop - scroll + mark.offsetHeight + 8,
      left: Math.max(0, Math.min(mark.offsetLeft, wrap.clientWidth - 344)),
    }
  }

  const open = (key: number | null) => {
    setActiveKey(key)
    setPos(placeFor(key))
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setActiveKey(null)
        setPos(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const syncScroll = () => {
    if (backRef.current && areaRef.current) backRef.current.scrollTop = areaRef.current.scrollTop
    if (activeKey !== null) setPos(placeFor(activeKey))
  }

  const pickAtCaret = () => {
    const caret = areaRef.current?.selectionStart ?? -1
    const hit = located.find((l) => caret >= l.start && caret <= l.end && areaRef.current?.selectionStart === areaRef.current?.selectionEnd)
    open(hit ? hit.key : null)
  }

  const text = 'px-4 py-3 text-sm leading-6 font-sans [scrollbar-gutter:stable]'

  return (
    <div ref={wrapRef} className={bare ? 'relative' : 'relative rounded-xl border border-white/10 bg-black/30 focus-within:border-violet-400'}>
      <div
        ref={backRef}
        aria-hidden="true"
        className={`pointer-events-none absolute inset-0 overflow-y-hidden whitespace-pre-wrap break-words text-transparent ${text}`}
      >
        {segments}
        {'\u200b'}
      </div>

      <textarea
        ref={areaRef}
        rows={rows}
        value={value}
        placeholder={placeholder}
        spellCheck={false}
        onChange={(event) => {
          open(null)
          onChange(event.target.value)
        }}
        onScroll={syncScroll}
        onClick={pickAtCaret}
        onKeyUp={(event) => !event.key.startsWith('Esc') && pickAtCaret()}
        className={`relative block w-full resize-none overflow-y-auto bg-transparent text-white caret-white outline-none focus-visible:outline-none placeholder:text-slate-600 ${text}`}
      />

      {active && pos && (
        <div
          role="dialog"
          aria-label="Suggestion"
          style={{ top: pos.top, left: pos.left }}
          className="rise absolute z-30 w-[21rem] rounded-2xl border border-white/10 bg-slate-900/95 p-4 text-left shadow-2xl shadow-black/60 backdrop-blur-xl"
        >
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                active.finding.severity === 'Critical'
                  ? 'bg-red-500'
                  : active.finding.severity === 'Warning'
                    ? 'bg-amber-300'
                    : 'bg-sky-400'
              }`}
            />
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              {active.finding.category}
            </span>
          </div>

          {active.finding.replacement !== undefined && (
            <p className="mt-3 text-sm">
              <span className="text-slate-500 line-through">{active.finding.quote}</span>
              <span className="mx-2 text-slate-500">→</span>
              <span className="font-semibold text-emerald-300">{active.finding.replacement || '(remove)'}</span>
            </p>
          )}

          <p className="mt-2 text-sm leading-6 text-slate-300">{active.finding.explanation}</p>
          <p className="mt-1 text-xs text-slate-500">Rule: {active.finding.guideline}</p>

          <div className="mt-4 flex items-center gap-2">
            {active.finding.replacement !== undefined ? (
              <button
                onClick={() => {
                  onApply(active.key)
                  open(null)
                }}
                className="btn-primary px-4 py-2 text-sm"
              >
                Apply fix
              </button>
            ) : (
              <span className="text-xs text-slate-400">{active.finding.suggestion}</span>
            )}
            <button
              onClick={() => {
                onDismiss(active.key)
                open(null)
              }}
              className="btn-ghost px-3 py-2 text-sm"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
