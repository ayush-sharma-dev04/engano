import { useState } from 'react'
import type { ReviewSubmission } from '../model'
import { useNameOf } from '../people'
import { Modal, Pill } from '../ui'
import { FIELD } from '../styles'

type Props = {
  submission: ReviewSubmission
  onBack: () => void
  onApprove: () => void
  onRequestChanges: (comment: string) => void
}

const DOT = { Critical: 'bg-red-500', Warning: 'bg-yellow-400', Suggestion: 'bg-blue-400' } as const
const BADGE = {
  Critical: 'bg-red-500/10 text-red-400',
  Warning: 'bg-yellow-400/10 text-yellow-300',
  Suggestion: 'bg-blue-400/10 text-blue-300',
} as const

/** One submission with ENGANO's findings, and the decision that fits who is looking. */
export default function SubmissionDetail({ submission, onBack, onApprove, onRequestChanges }: Props) {
  const nameOf = useNameOf()
  const [asking, setAsking] = useState(false)
  const [comment, setComment] = useState('')

  return (
    <div className="rise">
      <div className="mb-8 flex items-center justify-between gap-4">
        <div>
          <button onClick={onBack} className="mb-4 text-sm text-slate-400 hover:text-white">
            ← Back to Review Queue
          </button>
          <h1 className="text-2xl font-semibold">Review submission</h1>
          <p className="mt-1 text-sm text-slate-400">Check the content and ENGANO’s findings before deciding.</p>
        </div>
        <Pill tone={submission.status === 'Approved' ? 'good' : submission.status === 'Changes Requested' ? 'bad' : 'warn'}>
          {submission.status}
        </Pill>
      </div>

      <div className="glass mb-6 rounded-2xl p-6">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Submission</p>
        <h2 className="mt-2 text-xl font-semibold">{submission.title}</h2>
        <p className="mt-1 text-sm text-slate-500">
          Submitted {submission.submittedAt}
          {submission.creatorId ? ` by ${nameOf(submission.creatorId)}` : ''}
        </p>
      </div>

      <div className="glass mb-6 rounded-2xl p-6">
        <h2 className="text-lg font-semibold">Content</h2>
        <div className="mt-4 rounded-lg bg-slate-950 p-5">
          <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">{submission.content}</p>
        </div>
      </div>

      <div className="mb-4">
        <h2 className="text-lg font-semibold">ENGANO findings</h2>
        <p className="mt-1 text-sm text-slate-400">Automated findings to weigh before approving.</p>
      </div>

      <div className="space-y-4">
        {submission.findings.length === 0 && (
          <p className="rounded-xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-500">
            ENGANO did not flag anything on this draft.
          </p>
        )}
        {submission.findings.map((finding, index) => (
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

      <div className="glass mt-8 rounded-2xl p-6">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div>
            <h2 className="font-semibold">Reviewer decision</h2>
            <p className="mt-1 text-sm text-slate-400">
              Approve it, or reject it with a note so the creator knows what to fix.
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => setAsking(true)}
              className="rounded-lg border border-red-500/30 bg-red-500/5 px-5 py-3 text-sm font-semibold text-red-400 hover:bg-red-500/10"
            >
              Reject
            </button>
            <button onClick={onApprove} className="btn-primary px-5 py-3 text-sm">
              Approve
            </button>
          </div>
        </div>
      </div>

      {asking && (
        <Modal
          title="Reject draft"
          onClose={() => {
            setAsking(false)
            setComment('')
          }}
        >
          <p className="text-sm text-slate-400">Tell the creator what to change before this can be approved.</p>
          <textarea
            rows={5}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="e.g. Please remove the unsupported performance claim and use an approved statement."
            className={`${FIELD} mt-4 resize-none leading-6 focus:border-red-500`}
          />
          <div className="mt-6 flex justify-end gap-3">
            <button
              onClick={() => {
                setAsking(false)
                setComment('')
              }}
              className="btn-ghost px-4 py-2.5 text-sm text-slate-300"
            >
              Cancel
            </button>
            <button
              disabled={!comment.trim()}
              onClick={() => onRequestChanges(comment)}
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
