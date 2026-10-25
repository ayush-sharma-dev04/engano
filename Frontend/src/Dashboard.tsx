import { useState, type ReactNode } from 'react'
import { Navigate, Route, Routes, useNavigate, useParams } from 'react-router'
import type { Assignment, ReviewSubmission } from './model'
import { PeopleContext } from './people'
import { useEngano, type DraftOut } from './useEngano'
import type { SubmissionDetailData } from './appApi'
import Shell, { type NavItem } from './components/Shell'
import ServerAddress from './components/ServerAddress'
import BrandGuidelines from './components/BrandGuidelines'
import Insights from './components/Insights'
import ReviewQueue from './components/ReviewQueue'
import { Empty, Loader, PageHeader, Pill } from './ui'
import Studio from './pages/Studio'
import Assignments from './pages/Assignments'
import MySubmissions from './pages/MySubmissions'
import ReviewerHistory from './pages/ReviewerHistory'
import Workspaces from './pages/Workspaces'
import Overview from './pages/Overview'
import ApprovedDrafts from './pages/ApprovedDrafts'
import SubmissionDetail from './pages/SubmissionDetail'
import Settings from './pages/Settings'
import JoinWorkspace from './pages/JoinWorkspace'

type Props = { token: string; onLogout: () => void }

type Seed = { key: number; title: string; content: string; editingId: number | null }

/** One signed-in person's app: the screens and navigation depend on their role. */
export default function Dashboard({ token, onLogout }: Props) {
  const data = useEngano(token, onLogout)
  const nameOf = (id: string) => data.people[id] ?? 'Unknown user'
  const { role, joined, workspace } = data
  const navigate = useNavigate()
  const [seed, setSeed] = useState<Seed>({ key: 0, title: '', content: '', editingId: null })
  const [joining, setJoining] = useState(false)

  const pending = data.submissions.filter((s) => s.status === 'Pending Review').length
  const inWorkspace = role === 'Creator' && !!joined

  const nav: NavItem[] =
    role === 'Brand Manager'
      ? [
          { id: 'overview', label: 'Overview', icon: 'insights' },
          { id: 'workspaces', label: 'Workspaces', icon: 'workspace' },
          { id: 'approved', label: 'Approved drafts', icon: 'approvals' },
          { id: 'guidelines', label: 'Brand Guidelines', icon: 'guidelines' },
          { id: 'settings', label: 'Settings', icon: 'settings' },
        ]
      : role === 'Reviewer'
        ? [
            { id: 'queue', label: 'Review Queue', icon: 'queue', badge: pending },
            { id: 'history', label: 'History', icon: 'history' },
            { id: 'settings', label: 'Settings', icon: 'settings' },
          ]
        : inWorkspace
          ? [
              { id: 'studio', label: 'Studio', icon: 'studio' },
              { id: 'assignments', label: 'Assignments', icon: 'assignments' },
              { id: 'approvals', label: 'Approvals', icon: 'approvals' },
              { id: 'insights', label: 'Insights', icon: 'insights' },
              { id: 'settings', label: 'Settings', icon: 'settings' },
            ]
          : [
              { id: 'studio', label: 'Studio', icon: 'studio' },
              { id: 'brands', label: 'Find a brand', icon: 'workspace' },
              { id: 'settings', label: 'Settings', icon: 'settings' },
            ]

  const go = (id: string) => navigate(`/${id}`)

  const hasStudio = role === 'Creator'

  const startDraft = (next: Partial<Seed> = {}) => {
    setSeed((s) => ({ key: s.key + 1, title: '', content: '', editingId: null, ...next }))
    go('studio')
  }

  /** Returns true when the server accepted the draft, so the studio knows it can clear itself. */
  const submitStudio = async (draft: DraftOut): Promise<boolean> => {
    if (!joined) {
      setJoining(true)
      return false
    }
    const saved = await data.submitDraft(draft, seed.editingId)
    if (typeof saved === 'string') return false
    setSeed((s) => ({ key: s.key + 1, title: '', content: '', editingId: null }))
    go(saved.status === 'Approved' ? 'approvals' : 'assignments')
    return true
  }

  const startAssignment = (a: Assignment) => startDraft({ title: a.title })
  const editSubmission = (s: ReviewSubmission) => startDraft({ title: s.title, content: s.content, editingId: s.id })

  const decide = async (submission: ReviewSubmission, approve: boolean, comment = '') => {
    const problem = approve ? await data.approve(submission) : await data.reject(submission, comment)
    if (!problem) navigate('/queue')
  }

  const headerExtra =
    role === 'Creator' ? (
      joined ? (
        <Pill tone="good">{joined.name}</Pill>
      ) : data.pendingRequest ? (
        <button onClick={() => setJoining(true)} className="rounded-full bg-amber-400/10 px-3 py-1 text-xs font-medium text-amber-300">
          Waiting: {data.pendingRequest.name}
        </button>
      ) : (
        <button onClick={() => setJoining(true)} className="btn-ghost px-4 py-2 text-xs font-semibold text-violet-200">
          Join workspace
        </button>
      )
    ) : role === 'Brand Manager' && workspace ? (
      <Pill tone="good">{workspace.name}</Pill>
    ) : null

  if (!data.ready) {
    return (
      <div className="relative flex min-h-screen items-center justify-center text-white">
        <div className="aurora" aria-hidden="true" />
        <div className="relative z-10 text-center">
          {data.error ? <p className="text-sm text-slate-400">{data.error}</p> : <Loader label="Loading your workspace…" />}
          {data.error && <ServerAddress />}
          {data.error && (
            <button onClick={() => void data.refresh()} className="btn-primary mt-4 px-5 py-2.5 text-sm">
              Try again
            </button>
          )}
        </div>
      </div>
    )
  }

  const page = (id: string): ReactNode => {
    switch (id) {
      case 'brands':
        return (
          <div className="rise mx-auto max-w-2xl pt-10">
            <Empty
              title="Choose a brand to write for"
              action={
                <button onClick={() => setJoining(true)} className="btn-primary px-6 py-3 text-sm">
                  Browse brands
                </button>
              }
            >
              ENGANO checks your content against a brand’s approved guidelines and facts. Pick the brand you create for, or enter the code its
              Brand Manager gave you. Once they accept you, drafts are reviewed before anything is published.
            </Empty>
          </div>
        )
      case 'assignments':
        return joined ? (
          <Assignments workspace={joined} assignments={data.assignments} drafts={data.submissions} onStart={startAssignment} onNewDraft={() => startDraft()} />
        ) : null
      case 'workspaces':
        return (
          <Workspaces
            workspaces={data.managed}
            active={workspace}
            assignments={data.assignments}
            onOpen={data.setActiveId}
            onCreate={data.createWorkspace}
            onDelete={data.deleteWorkspace}
            onAnswerRequest={data.answerRequest}
            reviewerAccounts={data.myReviewers}
            onAddReviewer={data.addReviewer}
            onUpdateAssignment={data.updateAssignment}
            onDeleteAssignment={data.deleteAssignment}
            onCreateReviewer={(id, d) => data.createReviewer(id, d.name, d.email)}
            onRemoveMember={data.removeMember}
            onCreateAssignment={data.createAssignment}
          />
        )
      case 'queue':
        return <ReviewQueue submissions={data.submissions} onOpenSubmission={(s) => navigate(`/queue/${s.id}`)} />
      case 'approvals':
        return <MySubmissions submissions={data.submissions} onEdit={editSubmission} onOpen={(s) => navigate(`/approvals/${s.id}`)} />
      case 'history':
        return <ReviewerHistory userId={data.userId} actions={data.reviewerActions} />
      case 'guidelines':
        return workspace ? (
          <>
            <PageHeader kicker={workspace.name} title="Brand guidelines">
              These DO and DON’T rules are checked on every draft in this workspace, on top of the ENGANO brand policy.
            </PageHeader>
            <BrandGuidelines guidelines={data.guidelines} setGuidelines={data.setGuidelines} />
          </>
        ) : (
          <Empty title="Open a workspace first">Guidelines belong to a workspace. Pick one under Workspaces.</Empty>
        )
      case 'approved':
        return <ApprovedDrafts workspaces={data.managed} submissions={data.submissions} onOpen={(s) => navigate(`/approved/${s.id}`)} />
      case 'overview':
        return <Overview workspaces={data.managed} submissions={data.submissions} actions={data.reviewerActions} />
      case 'insights':
        return <Insights submissions={data.submissions} />
      case 'settings':
        return (
          <Settings
            name={nameOf(data.userId)}
            email={data.me?.email ?? ''}
            role={role}
            workspace={workspace}
            canLeave={inWorkspace}
            contact={role === 'Reviewer' && data.me ? { whatsapp: data.me.whatsapp, discordId: data.me.discordId } : undefined}
            onSaveContact={data.saveContact}
            onTestContact={data.testContact}
            onLeave={() => {
              data.leaveWorkspace()
              go('studio')
            }}
            onLogout={onLogout}
          />
        )
      default:
        return null
    }
  }

  const studio = hasStudio ? (
    <Studio
      key={seed.key}
      token={token}
      onSubmit={submitStudio}
      submitLabel={joined ? 'Send for review' : 'Join a brand to send'}
      seed={seed.title || seed.content ? { title: seed.title, content: seed.content } : undefined}
      subheading={workspace ? `Checked against ${workspace.name}’s brand guidelines and the ENGANO brand policy.` : undefined}
    />
  ) : null

  return (
    <PeopleContext.Provider value={data.people}>
      <Routes>
        <Route
          element={
            <Shell
              roleLabel={role}
              userName={nameOf(data.userId)}
              nav={nav}
              headerExtra={headerExtra}
              persistent={studio}
              persistentPath="/studio"
              notice={
                data.error ? (
                  <p role="alert" className="mx-auto mb-6 flex max-w-3xl items-start justify-between gap-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
                    <span>{data.error}</span>
                    <button onClick={data.clearError} aria-label="Dismiss" className="shrink-0 text-red-300 hover:text-white">
                      ✕
                    </button>
                  </p>
                ) : null
              }
              sidebarNote={
                role === 'Creator' && !joined ? (
                  <div className="glass mt-8 rounded-xl p-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Solo creator</p>
                    <p className="mt-2 text-xs leading-5 text-slate-400">
                      Join a workspace to get brand review, approvals and assignments from a Brand Manager.
                    </p>
                  </div>
                ) : null
              }
            />
          }
        >
          {nav.map((n) => (
            <Route key={n.id} path={n.id} element={n.id === 'studio' ? null : page(n.id)} />
          ))}
          {role === 'Reviewer' && (
            <Route path="queue/:id" element={<DraftRoute back={{ label: 'Back to Review Queue', to: '/queue' }} load={data.fetchDetail} onComment={data.comment} onDecide={decide} />} />
          )}
          {role === 'Creator' && (
            <Route
              path="approvals/:id"
              element={<DraftRoute back={{ label: 'Back to Approvals', to: '/approvals' }} load={data.fetchDetail} onComment={data.comment} onEdit={editSubmission} />}
            />
          )}
          {role === 'Brand Manager' && (
            <Route path="approved/:id" element={<DraftRoute back={{ label: 'Back to Approved drafts', to: '/approved' }} load={data.fetchDetail} onComment={data.comment} />} />
          )}
          <Route path="*" element={<Navigate to={`/${nav[0].id}`} replace />} />
        </Route>
      </Routes>

      {joining && !joined && (
        <JoinWorkspace
          directory={data.directory}
          pending={data.pendingRequest}
          onRequest={data.requestJoin}
          onCancelRequest={data.cancelRequest}
          onClose={() => setJoining(false)}
          onJoin={async (code) => {
            const problem = await data.joinWorkspace(code)
            if (!problem) go('studio')
            return problem
          }}
        />
      )}
    </PeopleContext.Provider>
  )
}

/** One draft, addressed by the URL (/queue/12, /approvals/12, /approved/12). What you can do depends on who you are. */
function DraftRoute({
  back,
  load,
  onComment,
  onDecide,
  onEdit,
}: {
  back: { label: string; to: string }
  load: (id: number) => Promise<SubmissionDetailData>
  onComment: (id: number, body: string) => Promise<string | null>
  onDecide?: (submission: ReviewSubmission, approve: boolean, comment?: string) => void
  onEdit?: (submission: ReviewSubmission) => void
}) {
  const { id } = useParams()
  const navigate = useNavigate()
  if (!id || Number.isNaN(Number(id))) return <Navigate to={back.to} replace />
  return (
    <SubmissionDetail
      key={id}
      id={Number(id)}
      load={load}
      onComment={onComment}
      backLabel={back.label}
      onBack={() => navigate(back.to)}
      onApprove={onDecide ? (s) => onDecide(s, true) : undefined}
      onReject={onDecide ? (s, comment) => onDecide(s, false, comment) : undefined}
      onEdit={onEdit}
    />
  )
}
