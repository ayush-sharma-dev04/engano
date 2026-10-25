import type { Guideline } from './App'
import type { ReviewSubmission } from './components/ReviewQueue'

// Account types: creators write for a brand, brand managers run it, reviewers are
// created by a brand manager and decide on escalated drafts.
export type Purpose = 'Content Creator' | 'Business' | 'Reviewer'
export type Role = 'Creator' | 'Reviewer' | 'Brand Manager'
export type ApprovalSource = 'AI' | 'Reviewer' | 'Brand Manager'
export type Member = {
  id: number
  userId: string
  role: 'Creator' | 'Reviewer'
}

export type Workspace = {
  id: number
  name: string
  code: string
  createdAt: string
  createdBy: string
  members: Member[]
  // People who asked to join and wait for the Brand Manager's answer.
  requests?: { id: number; userId: string }[]
}

export type Assignment = {
  id: number
  workspaceId: number
  title: string
  description: string
  dueDate: string
  createdAt: string
}

export type ReviewerAction = {
  id: number
  submissionId: number
  workspaceId: number | null
  title: string
  action: 'Direct Approval' | 'Request Changes'
  createdAt: string
  reviewerId?: string
  at?: number
}


export type { Guideline, ReviewSubmission }
