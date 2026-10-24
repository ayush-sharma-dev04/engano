import { useEffect, useRef, useState } from 'react'
import type { Finding } from '../App'
import type { Question, ReviewSummary, SiteInfo } from '../api'
import { Icon, Mascot } from '../ui'
import SuggestionEditor from './SuggestionEditor'
import { MAX_IMAGES, type AttachedImage } from '../images'

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
  answers: Record<string, string>
  onAnswer: (answers: Record<string, string>) => void
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
                  <h3 className="text-lg font-semibold">{VERDICT[summary.status].title}</h3>
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
