import { useEffect, useState } from 'react'
import type { Finding } from '../App'
import type { ReviewSummary } from '../api'
import { Icon, Mascot } from '../ui'
import SuggestionEditor from './SuggestionEditor'

const STEPS = [
  'Checking brand rules',
  'Checking claims and facts',
  'Checking tone',
  'Checking legal and policy',
  'Putting the review together',
]

const VERDICT = {
  RED: { title: 'Needs reviewer approval', tone: 'border-red-500/40 bg-red-500/10' },
  YELLOW: { title: 'Needs your input', tone: 'border-amber-400/40 bg-amber-400/10' },
  GREEN: { title: 'Ready to publish', tone: 'border-emerald-500/40 bg-emerald-500/10' },
} as const

const DOT = { Critical: 'bg-red-500', Warning: 'bg-amber-300', Suggestion: 'bg-sky-400' } as const

type Props = {
  title: string
  onTitle: (value: string) => void
  content: string
  onContent: (value: string) => void
  findings: Finding[]
  hidden: Set<number>
  onApply: (key: number) => void
  onDismiss: (key: number) => void
  onFixAll: () => void
  fixableCount: number
  started: boolean
  isReviewing: boolean
  summary: ReviewSummary | null
  error: string | null
  onRun: () => void
  onCancel: () => void
  onSubmit: () => void
}

/** Enough rows for the text at the bubble's width (about 68 characters per line). */
function bubbleRows(text: string): number {
  const lines = text.split('\n').reduce((sum, line) => sum + Math.max(1, Math.ceil(line.length / 68)), 0)
  return Math.min(16, Math.max(1, lines))
}

function Thinking() {
  const [step, setStep] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setStep((n) => (n + 1) % STEPS.length), 1800)
    return () => clearInterval(id)
  }, [])
  return (
    <span className="text-sm text-slate-400">
      {STEPS[step]}
      <span className="ml-1 inline-flex gap-[3px] align-middle">
        <i className="dot" />
        <i className="dot" style={{ animationDelay: '0.15s' }} />
        <i className="dot" style={{ animationDelay: '0.3s' }} />
      </span>
    </span>
  )
}

function IconButton({ label, icon, onClick }: { label: string; icon: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className="btn-ghost flex h-9 w-9 items-center justify-center text-slate-400"
    >
      <Icon name={icon} />
    </button>
  )
}

export default function StudioChat(props: Props) {
  const { content, findings, hidden, summary, started, isReviewing, error } = props
  const [copied, setCopied] = useState(false)
  const visible = findings.map((f, key) => ({ f, key })).filter(({ key }) => !hidden.has(key))

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(summary?.rewrite ?? content)
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    } catch {
      /* clipboard can be blocked; nothing to do */
    }
  }

  // ----- Before the first review: a single composer, like a prompt box
  if (!started) {
    return (
      <div className="rise mx-auto flex min-h-[calc(100vh-9rem)] max-w-2xl flex-col items-center justify-center">
        <h2 className="text-center text-4xl font-semibold tracking-tight">What are we reviewing today?</h2>

        <div className="composer mt-10 w-full p-5">
          <input
            value={props.title}
            onChange={(event) => props.onTitle(event.target.value)}
            placeholder="Title (optional), e.g. Nimbus DB launch post"
            className="mb-2 w-full bg-transparent text-sm font-medium text-slate-200 outline-none placeholder:text-slate-600"
          />
          <SuggestionEditor
            bare
            rows={6}
            value={content}
            onChange={props.onContent}
            findings={[]}
            hidden={hidden}
            onApply={props.onApply}
            onDismiss={props.onDismiss}
            placeholder="Paste or write your content…"
          />
          <div className="mt-3 flex items-center justify-between">
            <button onClick={props.onCancel} className="btn-ghost px-3 py-2 text-sm text-slate-400">
              Cancel
            </button>
            <button
              onClick={props.onRun}
              disabled={content.trim() === ''}
              aria-label="Run ENGANO Review"
              title="Run ENGANO Review"
              className="btn-primary flex h-10 w-10 items-center justify-center !rounded-full"
            >
              <Icon name="send" />
            </button>
          </div>
        </div>

        <p className="mt-5 flex items-center gap-2 text-xs text-slate-500">
          <Icon name="lock" className="h-3.5 w-3.5" />
          Checked against your brand policy. Nothing is published from here.
        </p>
      </div>
    )
  }

  // ----- Conversation: your draft on the right, ENGANO's review on the left
  return (
    <div className="mx-auto max-w-3xl pb-16">
      <div className="mb-6 flex justify-end">
        <button onClick={props.onCancel} className="btn-ghost flex items-center gap-2 px-3 py-2 text-sm text-slate-400">
          <Icon name="plus" className="h-4 w-4" />
          New draft
        </button>
      </div>

      {/* You */}
      <div className="rise relative z-20 flex justify-end">
        <div className="w-[min(100%,42rem)] rounded-3xl bg-slate-800/90 px-5 py-3.5 ring-1 ring-white/5">
          {props.title.trim() && <p className="mb-1 text-xs font-medium text-slate-400">{props.title}</p>}
          <SuggestionEditor
            bare
            rows={bubbleRows(content)}
            value={content}
            onChange={props.onContent}
            findings={findings}
            hidden={hidden}
            onApply={props.onApply}
            onDismiss={props.onDismiss}
          />
        </div>
      </div>

      {/* ENGANO */}
      <div className="mt-10">
        <p className="mb-3 pl-1">
          {isReviewing ? (
            <Thinking />
          ) : (
            <span className="text-sm text-slate-400">
              {error ? 'Review failed' : `Reviewed · ${visible.length} ${visible.length === 1 ? 'suggestion' : 'suggestions'} left`}
            </span>
          )}
        </p>

        <div className="flex gap-5">
          <Mascot thinking={isReviewing} />

          <div className="min-w-0 flex-1">
            {error && (
              <div className="rise rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>
            )}

            {summary && (
              <div className="rise space-y-4">
                <div className={`rounded-2xl border p-5 ${VERDICT[summary.status].tone}`}>
                  <h3 className="text-lg font-semibold">{VERDICT[summary.status].title}</h3>
                  {summary.reason && <p className="mt-1 text-sm text-slate-300">{summary.reason}</p>}
                  {summary.question && <p className="mt-2 text-sm text-slate-300">{summary.question}</p>}
                  {summary.rewrite && (
                    <div className="mt-4">
                      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Suggested rewrite</p>
                      <p className="mt-1 whitespace-pre-wrap rounded-xl bg-black/30 p-3 text-sm text-slate-200">{summary.rewrite}</p>
                      <button
                        onClick={() => props.onContent(summary.rewrite ?? '')}
                        className="mt-2 text-sm font-medium text-violet-300 hover:text-violet-200"
                      >
                        Use this rewrite
                      </button>
                    </div>
                  )}
                </div>

                {visible.map(({ f, key }) => (
                  <div key={key} className="glass rise rounded-2xl p-4">
                    <div className="flex items-center gap-2">
                      <span className={`h-2.5 w-2.5 rounded-full ${DOT[f.severity]}`} />
                      <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">{f.category}</span>
                      <span className="text-xs text-slate-500">· {f.severity}</span>
                    </div>
                    <p className="mt-2 text-sm">
                      <span className="font-medium">{f.issue}</span>
                      {f.replacement !== undefined && (
                        <>
                          <span className="mx-2 text-slate-500">→</span>
                          <span className="font-semibold text-emerald-300">{f.replacement || '(remove)'}</span>
                        </>
                      )}
                    </p>
                    <p className="mt-1.5 text-sm leading-6 text-slate-300">{f.explanation}</p>
                    <p className="mt-1 text-xs text-slate-500">Rule: {f.guideline}</p>
                    {f.replacement === undefined && !f.append && (
                      <p className="mt-2 text-sm text-slate-400">{f.suggestion}</p>
                    )}
                    <div className="mt-3 flex gap-2">
                      {(f.replacement !== undefined || f.append) && (
                        <button onClick={() => props.onApply(key)} className="btn-primary px-3 py-1.5 text-xs">
                          Apply fix
                        </button>
                      )}
                      <button onClick={() => props.onDismiss(key)} className="btn-ghost px-3 py-1.5 text-xs">
                        Dismiss
                      </button>
                    </div>
                  </div>
                ))}

                <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                  <div className="flex items-center gap-1">
                    <IconButton label={copied ? 'Copied' : 'Copy'} icon={copied ? 'check' : 'copy'} onClick={copy} />
                    <IconButton label="Review again" icon="refresh" onClick={props.onRun} />
                    {props.fixableCount > 0 && (
                      <button onClick={props.onFixAll} className="btn-ghost ml-1 px-3 py-2 text-sm">
                        Fix all ({props.fixableCount})
                      </button>
                    )}
                  </div>
                  <button onClick={props.onSubmit} className="btn-primary px-5 py-2.5 text-sm">
                    Submit for Review
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
