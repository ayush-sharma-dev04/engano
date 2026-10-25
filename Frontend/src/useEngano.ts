import { useCallback, useEffect, useRef, useState } from 'react'
import type { Finding } from './App'
import type { ReviewSummary } from './api'
import { ApiError, team, type Snapshot } from './appApi'
import type { Assignment, Guideline, ReviewSubmission, Role, Workspace } from './model'

/** What the studio hands over when the creator submits a draft. */
export type DraftOut = {
  title: string
  content: string
  findings: Finding[]
  summary: ReviewSummary | null
}

const POLL_MS = 3000

/**
 * Everything the signed-in person's screens need, kept in step with the server: workspaces and
 * join codes, assignments, guidelines, the submission pipeline. The server
 * decides what each role may see and do; this hook only asks, then refreshes. It also refreshes
 * every few seconds, so a reviewer's decision shows up for the creator without a reload.
 */
export function useEngano(token: string, onExpired: () => void) {
  const [snap, setSnap] = useState<Snapshot | null>(null)
  const [activeId, setActiveId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const api = useRef(team(token))
  const expired = useRef(onExpired)
  useEffect(() => {
    expired.current = onExpired
  })

  const refresh = useCallback(async () => {
    try {
      setSnap(await api.current.state())
      setError((e) => (e?.startsWith('Could not reach') ? null : e))
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) expired.current()
      else if (e instanceof Error) setError(e.message)
    }
  }, [])

  useEffect(() => {
    void refresh()
    const tick = () => {
      if (!document.hidden) void refresh()
    }
    const id = setInterval(tick, POLL_MS)
    window.addEventListener('focus', tick)
    return () => {
      clearInterval(id)
      window.removeEventListener('focus', tick)
    }
  }, [refresh])

  /** Run a change on the server, then refresh. Returns an error message, or null on success. */
  const act = useCallback(
    async (fn: () => Promise<unknown>, quiet = false): Promise<string | null> => {
      try {
        await fn()
        await refresh()
        setError(null)
        return null
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) expired.current()
        const message = e instanceof Error ? e.message : 'Something went wrong.'
        // `quiet`: the form that asked shows the message itself, so no second banner.
        if (!quiet) setError(message)
        return message
      }
    },
    [refresh]
  )

  const me = snap?.me ?? null
  const role: Role = me?.purpose === 'Business' ? 'Brand Manager' : me?.purpose === 'Reviewer' ? 'Reviewer' : 'Creator'
  const workspaces = (snap?.workspaces ?? []) as Workspace[]
  const managed = role === 'Brand Manager' ? workspaces : []
  const joined = role === 'Brand Manager' ? null : (workspaces[0] ?? null)
  const workspace = role === 'Brand Manager' ? (managed.find((w) => w.id === activeId) ?? managed[0] ?? null) : joined
  const guidelines: Guideline[] = workspace ? (snap?.guidelines[String(workspace.id)] ?? []) : []

  const setGuidelines = (next: Guideline[] | ((current: Guideline[]) => Guideline[])) => {
    if (!workspace || !snap) return
    const value = typeof next === 'function' ? next(guidelines) : next
    // Show the change at once; the server's copy replaces it on the refresh.
    setSnap({ ...snap, guidelines: { ...snap.guidelines, [String(workspace.id)]: value } })
    void act(() => api.current.setGuidelines(workspace.id, value))
  }

  return {
    ready: snap !== null,
    error,
    clearError: () => setError(null),
    me,
    userId: me?.id ?? '',
    people: snap?.people ?? {},
    role,
    workspaces,
    managed,
    joined,
    workspace,
    setActiveId,
    assignments: (snap?.assignments ?? []) as Assignment[],
    guidelines,
    setGuidelines,
    submissions: (snap?.submissions ?? []) as ReviewSubmission[],
    reviewerActions: snap?.reviewerActions ?? [],
    directory: snap?.directory ?? [],
    pendingRequest: snap?.pendingRequest ?? null,
    myReviewers: snap?.myReviewers ?? [],
    refresh,


    createWorkspace: async (name: string) => {
      let id: number | null = null
      const problem = await act(async () => {
        id = (await api.current.createWorkspace(name)).id
      })
      if (id !== null) setActiveId(id)
      return problem
    },
    deleteWorkspace: (id: number) => act(() => api.current.deleteWorkspace(id)),
    joinWorkspace: (code: string) => act(() => api.current.join(code), true),
    requestJoin: (id: number) => act(() => api.current.requestJoin(id), true),
    cancelRequest: () => act(() => api.current.cancelRequest()),
    answerRequest: (ws: number, request: number, accept: boolean) => act(() => api.current.answerRequest(ws, request, accept)),
    leaveWorkspace: () => act(() => api.current.leave()),
    removeMember: (ws: number, member: number) => act(() => api.current.removeMember(ws, member)),
    addReviewer: (ws: number, reviewerId: string) => act(() => api.current.addReviewer(ws, reviewerId)),
    createReviewer: async (ws: number, name: string, email: string): Promise<{ error: string } | { password: string }> => {
      let password = ''
      const problem = await act(async () => {
        password = (await api.current.createReviewer(ws, name, email)).password
      }, true)
      return problem ? { error: problem } : { password }
    },

    createAssignment: (ws: number, title: string, description: string, due: string) =>
      act(() => api.current.addAssignment(ws, title, description, due)),
    updateAssignment: (id: number, fields: { title: string; description: string; dueDate: string }) =>
      act(() => api.current.updateAssignment(id, fields.title, fields.description, fields.dueDate)),
    deleteAssignment: (id: number) => act(() => api.current.deleteAssignment(id)),

    /** Send a draft to the workspace. The server decides whether ENGANO cleared it or a reviewer must. */
    submitDraft: async (draft: DraftOut, editingId: number | null): Promise<ReviewSubmission | string> => {
      let saved: ReviewSubmission | null = null
      const problem = await act(async () => {
        saved = await api.current.submit({
          title: draft.title,
          content: draft.content,
          findings: draft.findings,
          ai_status: draft.summary?.status ?? null,
          receipt: draft.summary?.receipt ?? null,
          editing_id: editingId,
        })
      })
      return problem ?? (saved as unknown as ReviewSubmission)
    },
    /** Save where review requests should be sent. Returns an error message, or null. */
    saveContact: (whatsapp: string, discordId: string) => act(() => api.current.saveContact(whatsapp, discordId), true),
    /** Send a test message to the saved contacts: per-platform result, or an error string. */
    testContact: async (): Promise<Record<string, string> | string> => {
      try {
        return await api.current.testContact()
      } catch (e) {
        return e instanceof Error ? e.message : 'Could not send the test.'
      }
    },
    /** One draft with every version and its timeline. */
    fetchDetail: (id: number) => api.current.detail(id),
    /** Add a comment to a draft. Returns an error message, or null. */
    comment: (id: number, body: string) => act(() => api.current.comment(id, body), true),
    approve: (submission: ReviewSubmission) => act(() => api.current.approve(submission.id)),
    reject: (submission: ReviewSubmission, comment: string) => act(() => api.current.reject(submission.id, comment)),
  }
}
