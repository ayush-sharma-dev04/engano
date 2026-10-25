import { useEffect, useRef, useState } from 'react'
import type { EventInfo, SubmissionDetailData } from '../appApi'
import { wordDiff } from '../diff'
import type { ReviewSubmission } from '../model'
import { Loader, Modal, Pill } from '../ui'
import { FIELD } from '../styles'

type Props = {
  id: number
  load: (id: number) => Promise<SubmissionDetailData>
  onComment: (id: number, body: string) => Promise<string | null>
  backLabel: string
  onBack: () => void
  /** Reviewer: decide on a draft that is waiting. */
  onApprove?: (submission: ReviewSubmission) => void
  onReject?: (submission: ReviewSubmission, comment: string) => void
  /** Creator: take a draft that needs changes back to the studio. */
  onEdit?: (submission: ReviewSubmission) => void
}

const DOT = { Critical: 'bg-red-500', Warning: 'bg-yellow-400', Suggestion: 'bg-blue-400' } as const
const BADGE = {
  Critical: 'bg-red-500/10 text-red-400',
  Warning: 'bg-yellow-400/10 text-yellow-300',
  Suggestion: 'bg-blue-400/10 text-blue-300',
} as const
const STATUS_TONE = { Approved: 'good', 'Changes Requested': 'bad', 'Pending Review': 'warn' } as const
const VERDICT = { GREEN: 'ENGANO: looks clean', YELLOW: 'ENGANO: needs a look', RED: 'ENGANO: serious problems' } as const

const when = (ms: number) => new Date(ms).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })

/** What happened, in words. */
function describe(e: EventInfo): string {
  switch (e.kind) {
    case 'submitted':
      return `${e.by} sent version ${e.version} for review`
    case 'resubmitted':
      return `${e.by} sent version ${e.version} after changes`
    case 'cleared':
      return 'ENGANO cleared it: nothing was left to fix'
    case 'approved':
      return `${e.by} approved it`
    case 'rejected':
      return `${e.by} asked for changes`
    default:
      return `${e.by} commented`
  }
}

const EVENT_TONE: Record<EventInfo['kind'], string> = {
  submitted: 'bg-violet-400',
  resubmitted: 'bg-violet-400',
  cleared: 'bg-emerald-400',
  approved: 'bg-emerald-400',
  rejected: 'bg-red-400',
  comment: 'bg-sky-400',
}

/**
 * One draft: ENGANO's findings, every version with what changed, and the conversation about it.
 * Reviewers also get Approve / Reject here; the creator gets "Edit and resubmit" when changes were asked for.
 */
export default function SubmissionDetail({ id, load, onComment, backLabel, onBack, onApprove, onReject, onEdit }: Props) {
  const [data, setData] = useState<SubmissionDetailData | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [tab, setTab] = useState<'findings' | 'history' | 'comments'>('findings')
  const [picked, setPicked] = useState<number | null>(null)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [commentError, setCommentError] = useState<string | null>(null)
  const [asking, setAsking] = useState(false)
  const [note, setNote] = useState('')
  const loader = useRef(load)
  useEffect(() => {
    loader.current = load
  })

  // Load it, then keep it fresh so a reply from someone else shows up while this is open.
  useEffect(() => {
    let alive = true
    const run = () =>
      loader
        .current(id)
        .then((d) => alive && (setData(d), setProblem(null)))
        .catch((e) => alive && setProblem(e instanceof Error ? e.message : 'Could not load this draft.'))
    void run()
    const timer = setInterval(() => !document.hidden && void run(), 4000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [id])

  if (!data) {
    return (
      <div className="rise">
        <button onClick={onBack} className="mb-4 text-sm text-slate-400 hover:text-white">
          ← {backLabel}
        </button>
        {problem ? <p className="text-sm text-red-300">{problem}</p> : <div className="py-10"><Loader label="Loading the draft…" size={130} /></div>}
      </div>
    )
  }

  const { submission, versions, events } = data
  const latest = versions[versions.length - 1]
  const shown = versions.find((v) => v.version === (picked ?? latest.version)) ?? latest
  const before = versions.find((v) => v.version === shown.version - 1)
  const comments = events.filter((e) => e.kind === 'comment')
  const canDecide = submission.status === 'Pending Review' && !!onApprove && !!onReject

  const send = async () => {
    if (!text.trim() || sending) return
    setSending(true)
    setCommentError(null)
    const failed = await onComment(id, text)
    if (failed) setCommentError(failed)
    else {
      setText('')
      setData(await load(id))
    }
    setSending(false)
  }

  const TABS = [
    ['findings', 'Findings'],
    ['history', `History (${versions.length})`],
    ['comments', `Comments (${comments.length})`],
  ] as const

  return (
    <div className="rise">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <button onClick={onBack} className="mb-4 text-sm text-slate-400 hover:text-white">
            ← {backLabel}
          </button>
          <h1 className="text-2xl font-semibold">{submission.title}</h1>
          <p className="mt-1 text-sm text-slate-400">
            Version {latest.version} · sent {when(latest.at)} by {latest.by}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {submission.aiStatus && <Pill tone="info">{VERDICT[submission.aiStatus]}</Pill>}
          <Pill tone={STATUS_TONE[submission.status]}>{submission.status}</Pill>
        </div>
      </div>

      <div className="glass mb-6 rounded-2xl p-6">
        <h2 className="text-lg font-semibold">Content</h2>
        <div className="mt-4 rounded-lg bg-slate-950 p-5">
          <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">{submission.content}</p>
        </div>
      </div>

      <div className="mb-5 flex gap-1 border-b border-white/10" role="tablist">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition ${
              tab === key ? 'border-violet-400 text-white' : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'findings' && (
        <div className="space-y-4">
          {latest.findings.length === 0 && (
            <p className="rounded-xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-500">
              ENGANO did not flag anything on this version.
            </p>
          )}
          {latest.findings.map((finding, index) => (
            <div key={index} className="glass rounded-2xl p-5">
              <div className="flex items-start gap-3">
                <div className={`mt-1 h-3 w-3 shrink-0 rounded-full ${DOT[finding.severity]}`} />
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-semibold">{finding.issue}</h3>
                    <span className={`rounded-full px-2 py-1 text-xs font-medium ${BADGE[finding.severity]}`}>{finding.severity}</span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{finding.category}</p>
                </div>
              </div>
              <div className="mt-5 rounded-lg bg-slate-950/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Why ENGANO flagged this</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">{finding.explanation}</p>
              </div>
              <div className="mt-3 rounded-lg border border-white/10 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Guideline involved</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">{finding.guideline}</p>
              </div>
              <div className="mt-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Suggested correction</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">{finding.suggestion}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'history' && (
        <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
          <div>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Versions</h2>
            <ul className="space-y-2">
              {[...versions].reverse().map((v) => (
                <li key={v.version}>
                  <button
                    onClick={() => setPicked(v.version)}
                    aria-pressed={shown.version === v.version}
                    className={`w-full rounded-xl border px-4 py-3 text-left text-sm transition ${
                      shown.version === v.version ? 'border-violet-400/60 bg-violet-500/10' : 'border-white/10 bg-black/20 hover:border-white/20'
                    }`}
                  >
                    <span className="font-medium">Version {v.version}</span>
                    {v.version === latest.version && <span className="ml-2 text-xs text-violet-300">latest</span>}
                    <span className="mt-0.5 block text-xs text-slate-500">{when(v.at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-6">
            <div className="glass rounded-2xl p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">
                  Version {shown.version}
                  {before ? ` · changes from version ${before.version}` : ' · first version'}
                </h2>
                <div className="flex gap-2 text-xs">
                  <span className="rounded bg-emerald-500/15 px-2 py-1 text-emerald-300">added</span>
                  <span className="rounded bg-red-500/15 px-2 py-1 text-red-300 line-through">removed</span>
                </div>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Sent by {shown.by}, {when(shown.at)} · {shown.findings.filter((f) => f.category !== 'Brand Check').length} finding(s)
              </p>
              <p className="mt-4 whitespace-pre-wrap rounded-lg bg-slate-950 p-5 text-sm leading-7 text-slate-300">
                {before
                  ? wordDiff(before.content, shown.content).map((piece, i) =>
                      piece.kind === 'same' ? (
                        <span key={i}>{piece.text}</span>
                      ) : piece.kind === 'add' ? (
                        <ins key={i} className="rounded bg-emerald-500/20 text-emerald-200 no-underline">
                          {piece.text}
                        </ins>
                      ) : (
                        <del key={i} className="rounded bg-red-500/15 text-red-300">
                          {piece.text}
                        </del>
                      )
                    )
                  : shown.content}
              </p>
            </div>

            <div className="glass rounded-2xl p-6">
              <h2 className="text-lg font-semibold">Timeline</h2>
              <ol className="mt-5 space-y-5 border-l border-white/10 pl-6">
                {events.map((e) => (
                  <li key={e.id} className="relative">
                    <span className={`absolute -left-[31px] top-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-slate-950 ${EVENT_TONE[e.kind]}`} />
                    <p className="text-sm font-medium">{describe(e)}</p>
                    <p className="text-xs text-slate-500">{when(e.at)}</p>
                    {e.body && <p className="mt-2 whitespace-pre-wrap rounded-lg bg-black/30 p-3 text-sm leading-6 text-slate-300">{e.body}</p>}
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      )}

      {tab === 'comments' && (
        <div className="glass rounded-2xl p-6">
          <div className="space-y-4">
            {comments.length === 0 && <p className="text-sm text-slate-500">No comments yet. Ask a question or leave a note for the others on this draft.</p>}
            {comments.map((c) => (
              <div key={c.id} className="rounded-xl border border-white/10 bg-black/20 p-4">
                <p className="text-sm font-medium">
                  {c.by} <span className="ml-2 text-xs font-normal text-slate-500">{when(c.at)} · on version {c.version}</span>
                </p>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{c.body}</p>
              </div>
            ))}
          </div>
          <div className="mt-6 border-t border-white/5 pt-5">
            <textarea
              rows={3}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Write a comment…"
              aria-label="Write a comment"
              className={`${FIELD} resize-none leading-6`}
            />
            {commentError && (
              <p role="alert" className="mt-2 text-sm text-red-300">
                {commentError}
              </p>
            )}
            <div className="mt-3 flex justify-end">
              <button onClick={send} disabled={!text.trim() || sending} className="btn-primary px-5 py-2.5 text-sm">
                {sending ? 'Sending…' : 'Comment'}
              </button>
            </div>
          </div>
        </div>
      )}

      {canDecide && (
        <div className="glass mt-8 rounded-2xl p-6">
          <div className="flex flex-wrap items-center justify-between gap-6">
            <div>
              <h2 className="font-semibold">Reviewer decision</h2>
              <p className="mt-1 text-sm text-slate-400">Approve it, or reject it with a note so the creator knows what to fix.</p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setAsking(true)}
                className="rounded-lg border border-red-500/30 bg-red-500/5 px-5 py-3 text-sm font-semibold text-red-400 hover:bg-red-500/10"
              >
                Reject
              </button>
              <button onClick={() => onApprove?.(submission)} className="btn-primary px-5 py-3 text-sm">
                Approve
              </button>
            </div>
          </div>
        </div>
      )}

      {onEdit && submission.status === 'Changes Requested' && (
        <div className="mt-8 rounded-2xl border border-red-500/20 bg-red-500/5 p-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-red-300">Reviewer feedback</p>
          <p className="mt-2 text-sm leading-6 text-slate-300">{submission.reviewerComment || 'Changes were requested.'}</p>
          <button onClick={() => onEdit(submission)} className="btn-primary mt-4 px-5 py-2.5 text-sm">
            Edit &amp; resubmit
          </button>
        </div>
      )}

      {asking && (
        <Modal
          title="Reject draft"
          onClose={() => {
            setAsking(false)
            setNote('')
          }}
        >
          <p className="text-sm text-slate-400">Tell the creator what to change before this can be approved.</p>
          <textarea
            rows={5}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. Please remove the unsupported performance claim and use an approved statement."
            className={`${FIELD} mt-4 resize-none leading-6 focus:border-red-500`}
          />
          <div className="mt-6 flex justify-end gap-3">
            <button
              onClick={() => {
                setAsking(false)
                setNote('')
              }}
              className="btn-ghost px-4 py-2.5 text-sm text-slate-300"
            >
              Cancel
            </button>
            <button
              disabled={!note.trim()}
              onClick={() => onReject?.(submission, note)}
              className="rounded-lg bg-red-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-400 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Reject draft
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
