// Client for the accounts, workspaces and review-pipeline routes of the ENGANO backend.
import type { Assignment, Guideline, Member, Purpose, ReviewerAction, ReviewSubmission } from './model'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

export type Me = {
  id: string
  name: string
  email: string
  purpose: Purpose
  brand: string | null
  // Where a reviewer wants review requests sent (blank when not set).
  whatsapp: string
  discordId: string
}

export type ServerWorkspace = {
  id: number
  name: string
  code: string
  createdAt: string
  createdBy: string
  members: Member[]
  requests: { id: number; userId: string }[]
}

export type DirectoryEntry = {
  managerId: string
  managerName: string
  brand: string
  workspaces: { id: number; name: string }[]
}

export type Snapshot = {
  me: Me
  people: Record<string, string>
  workspaces: ServerWorkspace[]
  assignments: Assignment[]
  guidelines: Record<string, Guideline[]>
  submissions: ReviewSubmission[]
  reviewerActions: ReviewerAction[]
  directory: DirectoryEntry[]
  pendingRequest: { id: number; name: string } | null
  myReviewers: { id: string; name: string; email: string }[]
}

/** The server said no (or could not be reached). `status` is 401 when the sign-in has expired. */
export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function call<T>(method: string, path: string, token: string | null, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(`Could not reach the ENGANO backend at ${API_URL}. Is it running?`, 0)
  }
  if (!response.ok) {
    let detail = 'Something went wrong. Try again.'
    try {
      const data = (await response.json()) as { detail?: unknown }
      if (typeof data.detail === 'string') detail = data.detail
      else if (Array.isArray(data.detail)) detail = 'Please check what you entered and try again.'
    } catch {
      /* not JSON */
    }
    throw new ApiError(detail, response.status)
  }
  return (await response.json()) as T
}

export const auth = {
  signUp: (b: { name: string; email: string; password: string; purpose: Purpose; brand?: string }) =>
    call<{ token: string; me: Me }>('POST', '/api/auth/signup', null, b),
  signIn: (email: string, password: string) => call<{ token: string; me: Me }>('POST', '/api/auth/signin', null, { email, password }),
  signOut: (token: string) => call<unknown>('POST', '/api/auth/signout', token).catch(() => undefined),
}

export type DraftBody = {
  title: string
  content: string
  findings: unknown[]
  ai_status: string | null
  receipt: string | null
  editing_id: number | null
}

export function team(token: string) {
  return {
    state: () => call<Snapshot>('GET', '/api/app/state', token),
    createWorkspace: (name: string) => call<{ id: number }>('POST', '/api/app/workspaces', token, { name }),
    deleteWorkspace: (id: number) => call('DELETE', `/api/app/workspaces/${id}`, token),
    join: (code: string) => call('POST', '/api/app/join', token, { code }),
    requestJoin: (id: number) => call('POST', `/api/app/workspaces/${id}/request`, token),
    cancelRequest: () => call('DELETE', '/api/app/request', token),
    answerRequest: (ws: number, request: number, accept: boolean) =>
      call('POST', `/api/app/workspaces/${ws}/requests/${request}`, token, { accept }),
    leave: () => call('POST', '/api/app/leave', token),
    removeMember: (ws: number, member: number) => call('DELETE', `/api/app/workspaces/${ws}/members/${member}`, token),
    createReviewer: (ws: number, name: string, email: string) =>
      call<{ id: string; email: string; password: string }>('POST', `/api/app/workspaces/${ws}/reviewers`, token, { name, email }),
    addReviewer: (ws: number, reviewerId: string) =>
      call('POST', `/api/app/workspaces/${ws}/reviewers/existing`, token, { reviewer_id: reviewerId }),
    addAssignment: (ws: number, title: string, description: string, due: string) =>
      call('POST', `/api/app/workspaces/${ws}/assignments`, token, { title, description, due_date: due }),
    updateAssignment: (id: number, title: string, description: string, due: string) =>
      call('PUT', `/api/app/assignments/${id}`, token, { title, description, due_date: due }),
    deleteAssignment: (id: number) => call('DELETE', `/api/app/assignments/${id}`, token),
    setGuidelines: (ws: number, items: Guideline[]) =>
      call('PUT', `/api/app/workspaces/${ws}/guidelines`, token, { items: items.map(({ type, text }) => ({ type, text })) }),
    saveContact: (whatsapp: string, discordId: string) => call<Me>('PUT', '/api/app/me/contact', token, { whatsapp, discord_id: discordId }),
    testContact: () => call<Record<string, string>>('POST', '/api/app/me/contact/test', token),
    submit: (b: DraftBody) => call<ReviewSubmission>('POST', '/api/app/submissions', token, b),
    approve: (id: number) => call('POST', `/api/app/submissions/${id}/approve`, token),
    reject: (id: number, comment: string) => call('POST', `/api/app/submissions/${id}/reject`, token, { comment }),
  }
}
