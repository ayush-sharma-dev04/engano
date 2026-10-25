import { useEffect, useRef, useState } from 'react'
import type { Finding } from '../App'
import type { Question, ReviewSummary, SiteInfo } from '../api'
import { Icon, Mascot } from '../ui'
import SuggestionEditor from './SuggestionEditor'
import { MAX_IMAGES, type AttachedImage } from '../images'
import { firstLink } from '../links'
import type { Linked, Turn } from '../turns'

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

/** What ENGANO did on a website and what it made of it, from the facts it measured. */
function SiteReport({ site }: { site: SiteInfo }) {
  const f = site.facts as Record<string, unknown>
  const num = (k: string) => (typeof f[k] === 'number' ? (f[k] as number) : 0)
  const list = (k: string): string[] => (Array.isArray(f[k]) ? (f[k] as unknown[]).map(String) : [])
  const did: string[] = []
  if (num('scrolledScreens')) did.push(`Scrolled through ${num('scrolledScreens')} screen(s) from top to bottom${f.backAtTop === false ? ' (it would not scroll back up)' : ' and back up'}`)
  if (num('linksChecked')) did.push(`Tested ${num('linksChecked')} links: ${num('brokenLinkCount') ? `${num('brokenLinkCount')} broken` : 'none broken'}`)
  if (f.mobileChecked) did.push(num('mobileOverflowPx') > 4 ? `Opened it phone-sized: it is ${num('mobileOverflowPx')}px too wide` : 'Opened it phone-sized: it fits the screen')
  if (num('httpStatus')) did.push(`The address answered with HTTP ${num('httpStatus')}`)
  const outline = list('outline')
  const nav = list('navLinks')
  const ctas = list('ctas')
  if (!did.length && !outline.length) return null
  return (
    <div className="grid gap-4 rounded-xl border border-white/10 bg-black/20 p-4 text-sm sm:grid-cols-2">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">What ENGANO did</p>
        <ul className="mt-1.5 list-disc space-y-1 pl-5 text-slate-200">
          {did.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
      </div>
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">What it found on the page</p>
        {outline.length > 0 && (
          <p className="mt-1.5 text-slate-200">
            <span className="text-slate-400">Headings: </span>
            {outline.slice(0, 6).map((h) => h.replace(/^H(\d) /, '')).join(' · ')}
          </p>
        )}
        {nav.length > 0 && (
          <p className="mt-1 text-slate-200">
            <span className="text-slate-400">Menu: </span>
            {nav.slice(0, 8).join(' · ')}
          </p>
        )}
        {ctas.length > 0 && (
          <p className="mt-1 text-slate-200">
            <span className="text-slate-400">Buttons: </span>
            {ctas.slice(0, 6).join(' · ')}
          </p>
        )}
      </div>
    </div>
  )
}

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
  siteMode: boolean
  onSiteMode: (on: boolean) => void
  siteUrl: string
  onSiteUrl: (url: string) => void
  site: SiteInfo | null
  images: AttachedImage[]
  attachError: string | null
  onAddImages: (files: File[]) => void
  onRemoveImage: (id: string) => void
  onAlt: (id: string, alt: string) => void
  history: Turn[]
  linked: Linked | null
  onFollowUp: (text: string) => void
  answers: Record<string, string>
  onAnswer: (answers: Record<string, string>) => void
  onCancel: () => void
  onSubmit: () => void
  submitLabel?: string
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

function Thumbnails({
  images,
  onRemove,
  onAlt,
  editable,
}: {
  images: AttachedImage[]
  onRemove?: (id: string) => void
  onAlt: (id: string, alt: string) => void
  editable: boolean
}) {
  if (images.length === 0) return null
  return (
    <div className="mb-3 flex flex-wrap gap-3">
      {images.map((image, index) => (
        <div key={image.id} className="w-36">
          <div className="relative">
            <img src={image.preview} alt={image.alt || image.name} className="h-24 w-36 rounded-xl object-cover ring-1 ring-white/10" />
            <span className="absolute left-1.5 top-1.5 rounded-full bg-black/60 px-2 py-0.5 text-[11px] text-white">
              Image {index + 1}
            </span>
            {onRemove && (
              <button
                onClick={() => onRemove(image.id)}
                aria-label={`Remove image ${index + 1}`}
                className="absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-black/60 text-xs text-white hover:bg-black/80"
              >
                ✕
              </button>
            )}
          </div>
          <input
            value={image.alt}
            onChange={(event) => onAlt(image.id, event.target.value)}
            readOnly={!editable}
            placeholder="Alt text"
            aria-label={`Alt text for image ${index + 1}`}
            className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/30 px-2.5 py-1.5 text-xs text-slate-200 outline-none placeholder:text-slate-600 focus:border-violet-400"
          />
        </div>
      ))}
    </div>
  )
}

const PLACEHOLDER: Record<Question['kind'], string> = {
  confirm_brand: '',
  website: 'https://yourcompany.com',
  evidence: 'Benchmark name or a link',
}

function QuestionsCard({ questions, onSend }: { questions: Question[]; onSend: (answers: Record<string, string>) => void }) {
  const [values, setValues] = useState<Record<string, string>>({})
  const filled = Object.fromEntries(Object.entries(values).filter(([, v]) => v.trim()))
  const set = (id: string, value: string) => setValues((current) => ({ ...current, [id]: value }))

  return (
    <div className="rise rounded-2xl border border-violet-400/40 bg-violet-500/10 p-5">
      <h3 className="text-lg font-semibold">I need a bit more information</h3>
      <p className="mt-1 text-sm text-slate-400">Answer what you can. I'll check your draft again with it.</p>

      <div className="mt-4 space-y-5">
        {questions.map((q) => (
          <div key={q.id}>
            <p className="text-sm leading-6 text-slate-200">{q.text}</p>
            {q.choices.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {q.choices.map((choice) => (
                  <button
                    key={choice}
                    onClick={() => set(q.id, choice)}
                    className={`rounded-xl border px-4 py-2 text-sm transition-colors ${
                      values[q.id] === choice
                        ? 'border-violet-400 bg-violet-500/30 text-white'
                        : 'border-white/10 text-slate-300 hover:bg-white/5'
                    }`}
                  >
                    {choice}
                  </button>
                ))}
              </div>
            ) : (
              <input
                value={values[q.id] ?? ''}
                onChange={(event) => set(q.id, event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && Object.keys(filled).length > 0 && onSend(filled)}
                placeholder={PLACEHOLDER[q.kind]}
                aria-label={q.text}
                className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none placeholder:text-slate-600 focus:border-violet-400"
              />
            )}
          </div>
        ))}
      </div>

      <div className="mt-5 flex justify-end">
        <button onClick={() => onSend(filled)} disabled={Object.keys(filled).length === 0} className="btn-primary px-5 py-2.5 text-sm">
          Send answers
        </button>
      </div>
    </div>
  )
}

const ANSWER_LABEL = (id: string) => (id === 'website' ? 'Website' : id === 'brand' ? 'Brand' : 'Source')

function MiniFinding({ f }: { f: Finding }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${DOT[f.severity]}`} />
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{f.category}</span>
        <span className="text-[11px] text-slate-500">· {f.severity}</span>
      </div>
      <p className="mt-1.5 text-sm font-medium">{f.issue}</p>
      <p className="mt-1 text-sm leading-6 text-slate-300">{f.explanation}</p>
    </div>
  )
}

function VerdictChip({ summary }: { summary: ReviewSummary }) {
  return (
    <span className={`rounded-full border px-3 py-1 text-xs font-medium ${VERDICT[summary.status].tone}`}>
      {VERDICT[summary.status].title}
    </span>
  )
}

/** The page behind a link in the message: it loads in the background while the text review is already on screen. */
function LinkedBlock({ linked }: { linked: Linked }) {
  return (
    <div className="glass rise rounded-2xl p-5">
      <p className="flex items-center gap-2 text-sm font-semibold">
        <Icon name="globe" className="h-4 w-4 text-slate-400" />
        The link in your message
      </p>
      <p className="mt-0.5 break-all text-xs text-slate-500">{linked.url}</p>

      {linked.status === 'loading' && (
        <p className="mt-3 text-sm text-slate-400">
          Opening the page and checking it
          <span className="ml-1 inline-flex gap-[3px] align-middle">
            <i className="dot" />
            <i className="dot" style={{ animationDelay: '0.15s' }} />
            <i className="dot" style={{ animationDelay: '0.3s' }} />
          </span>
          <span className="block text-xs text-slate-500">This can take a minute. Everything above is already final.</span>
        </p>
      )}

      {linked.status === 'error' && <p className="mt-3 text-sm text-red-300">{linked.error}</p>}

      {linked.status === 'done' && linked.site && linked.summary && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <VerdictChip summary={linked.summary} />
            <span className="text-xs text-slate-500">{linked.site.title}</span>
          </div>
          <img
            src={linked.site.screenshot}
            alt={`Screenshot of ${linked.site.url}`}
            className="max-h-56 w-full rounded-xl object-cover object-top ring-1 ring-white/10"
          />
          <SiteReport site={linked.site} />
          {linked.site.designNotes.length > 0 && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Design suggestions (AI advice)</p>
              <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-200">
                {linked.site.designNotes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          )}
          {(linked.findings ?? []).map((f, i) => (
            <MiniFinding key={i} f={f} />
          ))}
        </div>
      )}
    </div>
  )
}

/** An earlier message and its review, kept above the live one. */
function PastTurn({ turn }: { turn: Turn }) {
  const [open, setOpen] = useState(false)
  const shown = turn.findings.filter((_, key) => !turn.hidden.has(key))
  return (
    <div className="mb-10">
      <div className="flex justify-end">
        <div className="w-[min(100%,42rem)] rounded-3xl bg-slate-800/60 px-5 py-3.5 ring-1 ring-white/5">
          {turn.site && (
            <p className="mb-1 flex items-center gap-2 text-sm text-slate-300">
              <Icon name="globe" className="h-4 w-4 text-slate-500" />
              <span className="break-all">{turn.site.url}</span>
            </p>
          )}
          {turn.images.length > 0 && <Thumbnails images={turn.images} onAlt={() => {}} editable={false} />}
          {turn.content.trim() && <p className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-200">{turn.content}</p>}
        </div>
      </div>
      <div className="mt-3 flex items-start gap-3 pl-1">
        <Mascot width={56} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            {turn.summary ? <VerdictChip summary={turn.summary} /> : <span className="text-xs text-red-300">{turn.error ?? 'No result'}</span>}
            <span className="text-xs text-slate-500">
              {shown.length} {shown.length === 1 ? 'suggestion' : 'suggestions'}
              {turn.linked?.status === 'loading' ? ' · still checking the link' : ''}
            </span>
            {(shown.length > 0 || turn.linked) && (
              <button onClick={() => setOpen((o) => !o)} className="text-xs text-violet-300 hover:text-violet-200">
                {open ? 'Hide details' : 'Show details'}
              </button>
            )}
          </div>
          {open && (
            <div className="mt-3 space-y-2">
              {shown.map((f, i) => (
                <MiniFinding key={i} f={f} />
              ))}
              {turn.linked && <LinkedBlock linked={turn.linked} />}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/** The box that stays at the bottom, so the creator can keep drafting after each review. */
function FollowUpComposer({ disabled, onSend }: { disabled: boolean; onSend: (text: string) => void }) {
  const [text, setText] = useState('')
  const link = firstLink(text)
  const send = () => {
    if (!text.trim() || disabled) return
    onSend(text)
    setText('')
  }
  return (
    <div className="composer p-4">
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            send()
          }
        }}
        rows={Math.min(6, Math.max(1, text.split('\n').length))}
        placeholder="Draft another message… paste a link and I'll check that page too"
        aria-label="Draft another message"
        className="block w-full resize-none bg-transparent text-sm leading-6 text-white outline-none placeholder:text-slate-500 focus-visible:outline-none"
      />
      <div className="mt-2 flex items-center justify-between gap-3">
        <span className="min-w-0 truncate text-xs text-slate-500">
          {link ? (
            <span className="inline-flex items-center gap-1.5 text-violet-300">
              <Icon name="globe" className="h-3.5 w-3.5" />
              I'll also check {link.replace(/^https?:\/\//i, '').slice(0, 48)}
            </span>
          ) : disabled ? (
            'Reviewing…'
          ) : (
            'Enter to send, Shift+Enter for a new line'
          )}
        </span>
        <button
          onClick={send}
          disabled={disabled || !text.trim()}
          aria-label="Send message"
          title="Send"
          className="btn-primary flex h-9 w-9 shrink-0 items-center justify-center !rounded-full"
        >
          <Icon name="send" />
        </button>
      </div>
    </div>
  )
}

export default function StudioChat(props: Props) {
  const { content, findings, hidden, summary, started, isReviewing, error } = props
  const [copied, setCopied] = useState(false)
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
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

        <div
          className={`composer mt-10 w-full p-5 ${dragging ? '!border-violet-300 !bg-violet-500/10' : ''}`}
          onDragOver={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragging(false)
            props.onAddImages(Array.from(event.dataTransfer.files))
          }}
          onPaste={(event) => {
            const files = Array.from(event.clipboardData.files).filter((file) => file.type.startsWith('image/'))
            if (files.length) {
              event.preventDefault()
              props.onAddImages(files)
            }
          }}
        >
          {props.siteMode ? (
            <div>
              <label className="text-sm font-medium text-slate-200" htmlFor="site-url">
                Website address
              </label>
              <input
                id="site-url"
                value={props.siteUrl}
                onChange={(event) => props.onSiteUrl(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && props.siteUrl.trim() && props.onRun()}
                placeholder="https://yourcompany.com"
                autoFocus
                className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-violet-400"
              />
              <p className="mt-2 text-xs text-slate-500">
                ENGANO opens the page in a browser, reads it, looks at it, and tells you what to change. Public websites only.
              </p>
            </div>
          ) : (
            <>
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
            </>
          )}
          {!props.siteMode && <Thumbnails images={props.images} onRemove={props.onRemoveImage} onAlt={props.onAlt} editable />}
          {props.attachError && <p className="mb-2 text-xs text-red-300">{props.attachError}</p>}
          <input
            ref={fileInput}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            multiple
            hidden
            aria-label="Attach images"
            onChange={(event) => {
              props.onAddImages(Array.from(event.target.files ?? []))
              event.target.value = ''
            }}
          />
          <div className="mt-3 flex items-center justify-between">
            <div className="flex items-center gap-1">
              <button
                onClick={() => props.onSiteMode(!props.siteMode)}
                aria-label={props.siteMode ? 'Review text instead' : 'Check a website'}
                aria-pressed={props.siteMode}
                title={props.siteMode ? 'Back to text and images' : 'Check a website'}
                className={`btn-ghost flex h-10 w-10 items-center justify-center ${props.siteMode ? '!bg-violet-500/25 text-white' : 'text-slate-400'}`}
              >
                <Icon name="globe" />
              </button>
              <button
                onClick={() => fileInput.current?.click()}
                disabled={props.images.length >= MAX_IMAGES || props.siteMode}
                aria-label="Attach image"
                title="Attach an image (or drop / paste one)"
                className="btn-ghost flex h-10 w-10 items-center justify-center text-slate-400 disabled:opacity-40"
              >
                <Icon name="image" />
              </button>
              <button onClick={props.onCancel} className="btn-ghost px-3 py-2 text-sm text-slate-400">
                Cancel
              </button>
            </div>
            <button
              onClick={() => props.onRun()}
              disabled={props.siteMode ? props.siteUrl.trim() === '' : content.trim() === '' && props.images.length === 0}
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

      {props.history.map((turn) => (
        <PastTurn key={turn.id} turn={turn} />
      ))}

      {/* You */}
      <div className="rise relative z-20 flex justify-end">
        <div className="w-[min(100%,42rem)] rounded-3xl bg-slate-800/90 px-5 py-3.5 ring-1 ring-white/5">
          {props.site || props.siteMode ? (
            <div>
              <p className="flex items-center gap-2 text-sm text-slate-200">
                <Icon name="globe" className="h-4 w-4 text-slate-400" />
                <span className="break-all">{props.site?.url ?? props.siteUrl}</span>
              </p>
              {props.site && (
                <img
                  src={props.site.screenshot}
                  alt={`Screenshot of ${props.site.url}`}
                  className="mt-3 w-full rounded-xl ring-1 ring-white/10"
                />
              )}
              {props.site && <div className="mt-3"><SiteReport site={props.site} /></div>}
            </div>
          ) : null}
          {props.title.trim() && !props.siteMode && <p className="mb-1 text-xs font-medium text-slate-400">{props.title}</p>}
          {!props.siteMode && <Thumbnails images={props.images} onAlt={props.onAlt} editable />}
          {!props.siteMode && (content.trim() !== '' || props.images.length === 0) && <SuggestionEditor
            bare
            rows={bubbleRows(content)}
            value={content}
            onChange={props.onContent}
            findings={findings}
            hidden={hidden}
            onApply={props.onApply}
            onDismiss={props.onDismiss}
          />}
        </div>
      </div>

      {Object.keys(props.answers).length > 0 && (
        <div className="mt-2 flex flex-wrap justify-end gap-2">
          {Object.entries(props.answers).map(([id, value]) => (
            <span key={id} className="max-w-xs truncate rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
              <span className="text-slate-500">{ANSWER_LABEL(id)}: </span>
              {value}
            </span>
          ))}
        </div>
      )}

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
                {summary.questions.length > 0 && (
                  <QuestionsCard
                    key={summary.questions.map((q) => q.id).join('|')}
                    questions={summary.questions}
                    onSend={props.onAnswer}
                  />
                )}

                <div className={`rounded-2xl border p-5 ${VERDICT[summary.status].tone}`}>
                  <h3 className="text-lg font-semibold">{props.site && summary.status === 'RED' ? 'Fix these before it can pass' : VERDICT[summary.status].title}</h3>
                  {summary.reason && <p className="mt-1 text-sm text-slate-300">{summary.reason}</p>}
                  {summary.question && summary.questions.length === 0 && (
                    <p className="mt-2 text-sm text-slate-300">{summary.question}</p>
                  )}
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

                {props.site && (
                  <div className="glass rise rounded-2xl p-5">
                    <h3 className="text-lg font-semibold">Design suggestions</h3>
                    <p className="mt-1 text-xs text-slate-500">
                      The AI's opinion from the screenshot. Treat it as advice, not a rule.
                    </p>
                    {props.site.designNotes.length > 0 ? (
                      <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-200">
                        {props.site.designNotes.map((note) => (
                          <li key={note}>{note}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-3 text-sm text-slate-400">
                        {props.site.designError
                          ? `The AI couldn't review the design this time (${props.site.designError}).`
                          : 'The AI model is off, so there are no design suggestions. The measured checks below still ran.'}
                      </p>
                    )}
                  </div>
                )}

                {visible.map(({ f, key }) => (
                  <div key={key} className="glass rise rounded-2xl p-4">
                    <div className="flex items-center gap-2">
                      <span className={`h-2.5 w-2.5 rounded-full ${DOT[f.severity]}`} />
                      <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">{f.category}</span>
                      <span className="text-xs text-slate-500">· {f.severity}</span>
                      {f.imageIndex !== undefined && (
                        <span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-slate-300">
                          Image {f.imageIndex}
                        </span>
                      )}
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
                    {f.replacement === undefined && !f.append && !f.suggestedAlt && f.imageIndex === undefined && (
                      <p className="mt-2 text-sm text-slate-400">{f.suggestion}</p>
                    )}
                    {f.suggestedAlt && (
                      <p className="mt-2 text-sm text-slate-400">
                        Suggested alt text: <span className="text-slate-200">“{f.suggestedAlt}”</span>
                      </p>
                    )}
                    <div className="mt-3 flex gap-2">
                      {(f.replacement !== undefined || f.append) && (
                        <button onClick={() => props.onApply(key)} className="btn-primary px-3 py-1.5 text-xs">
                          Apply fix
                        </button>
                      )}
                      {f.imageIndex !== undefined && f.suggestedAlt && props.images[f.imageIndex - 1] && (
                        <button
                          onClick={() => props.onAlt(props.images[f.imageIndex! - 1].id, f.suggestedAlt!)}
                          className="btn-primary px-3 py-1.5 text-xs"
                        >
                          Use this alt text
                        </button>
                      )}
                      <button onClick={() => props.onDismiss(key)} className="btn-ghost px-3 py-1.5 text-xs">
                        Dismiss
                      </button>
                    </div>
                  </div>
                ))}

                {props.linked && <LinkedBlock linked={props.linked} />}

                <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                  <div className="flex items-center gap-1">
                    <IconButton label={copied ? 'Copied' : 'Copy'} icon={copied ? 'check' : 'copy'} onClick={copy} />
                    <IconButton label="Review again" icon="refresh" onClick={() => props.onRun()} />
                    {props.fixableCount > 0 && (
                      <button onClick={props.onFixAll} className="btn-ghost ml-1 px-3 py-2 text-sm">
                        Fix all ({props.fixableCount})
                      </button>
                    )}
                  </div>
                  <button onClick={props.onSubmit} className="btn-primary px-5 py-2.5 text-sm">
                    {props.submitLabel ?? 'Submit for Review'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Keep drafting */}
      <div className="sticky bottom-4 z-30 mt-10">
        <FollowUpComposer disabled={isReviewing} onSend={props.onFollowUp} />
      </div>
    </div>
  )
}
