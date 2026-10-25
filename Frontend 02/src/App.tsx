import { useState, type Dispatch, type FormEvent, type SetStateAction } from 'react'
import BrandGuidelines from './components/BrandGuidelines'
import ReviewQueue, {
  type ReviewSubmission,
} from './components/ReviewQueue'
import Insights from './components/Insights'

export type Finding = {
  severity: 'Critical' | 'Warning' | 'Suggestion'
  category: string
  issue: string
  explanation: string
  guideline: string
  suggestion: string
}

export type Guideline = {
  id: number
  type: 'DO' | "DON'T"
  text: string
}

type Purpose = 'Content Creator' | 'Business'

type WorkspaceMemberRole = 'Creator' | 'Reviewer'

type WorkspaceMember = {
  id: number
  userId: string
  role: WorkspaceMemberRole
}

type Workspace = {
  id: number
  name: string
  code: string
  createdAt: string
  createdBy: string
  members: WorkspaceMember[]
}

type WorkspaceAssignment = {
  id: number
  workspaceId: number
  title: string
  description: string
  dueDate: string
  createdAt: string
}

type ReviewerAction = {
  id: number
  submissionId: number
  workspaceId: number | null
  title: string
  action: 'Direct Approval' | 'Request Changes'
  createdAt: string
}

type ApprovalSource = 'AI' | 'Reviewer' | 'Brand Manager'

function App() {
  // ==========================================
  // AUTHENTICATION
  // ==========================================

  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [email, setEmail] = useState('')
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  // ==========================================
  // PURPOSE
  // ==========================================

  const [selectedPurpose, setSelectedPurpose] =
    useState<Purpose | null>(null)

  const [purposeConfirmed, setPurposeConfirmed] = useState(false)

  // ==========================================
  // NAVIGATION
  // ==========================================

  const [activePage, setActivePage] = useState('studio')

  // ==========================================
  // WORKSPACE
  // ==========================================

  const [workspaceName, setWorkspaceName] = useState('')
  const [, setWorkspaceCode] = useState('')

  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null)
  const [workspaceJoined, setWorkspaceJoined] = useState(false)

  const [workspaceCodeInput, setWorkspaceCodeInput] =
    useState('')

  const [showJoinWorkspaceModal, setShowJoinWorkspaceModal] =
    useState(false)

  const [workspaceMessage, setWorkspaceMessage] = useState('')

  const [workspaceMembers, setWorkspaceMembers] =
    useState<WorkspaceMember[]>([])

  const [selectedReviewerId, setSelectedReviewerId] =
    useState<number | null>(null)

  const [workspaceAssignments, setWorkspaceAssignments] =
    useState<WorkspaceAssignment[]>([])

  const [assignmentTitle, setAssignmentTitle] = useState('')
  const [assignmentDescription, setAssignmentDescription] = useState('')
  const [assignmentDueDate, setAssignmentDueDate] = useState('')

  // ==========================================
  // CREATOR SETTINGS
  // ==========================================

  const [autoSpelling, setAutoSpelling] = useState(false)
  const [autoGrammar, setAutoGrammar] = useState(false)

  // ==========================================
  // CREATOR DASHBOARD
  // ==========================================

  const [creatorPlatform, setCreatorPlatform] =
    useState('Instagram')

  const [creatorDraft, setCreatorDraft] = useState('')

  const [creatorImproved, setCreatorImproved] =
    useState('')

  const [creatorMessage, setCreatorMessage] =
    useState('')

  const [isCreatorImproving, setIsCreatorImproving] =
    useState(false)

  type CreatorHistoryItem = {
    id: number
    platform: string
    input: string
    output: string
    createdAt: string
  }

  const [creatorHistory, setCreatorHistory] =
    useState<CreatorHistoryItem[]>([])

  const [editingSubmissionId, setEditingSubmissionId] =
    useState<number | null>(null)

  const [approvalFilter, setApprovalFilter] =
    useState<'All' | 'Request Changes' | 'Approved'>('All')

  // ==========================================
  // STUDIO / BRAND REVIEW
  // ==========================================

  const [isCreatingDraft, setIsCreatingDraft] =
    useState(false)

  const [isReviewing, setIsReviewing] =
    useState(false)

  const [draftTitle, setDraftTitle] = useState('')

  const [content, setContent] = useState('')

  const [findings, setFindings] =
    useState<Finding[]>([])

  const [aiConfidence, setAiConfidence] =
    useState<number | null>(null)

  const [needsHumanReview, setNeedsHumanReview] =
    useState(false)

  // ==========================================
  // SHARED BRAND GUIDELINES
  // ==========================================

  const [guidelines, setGuidelines] =
    useState<Guideline[]>([])

  const [workspaceGuidelines, setWorkspaceGuidelinesState] =
    useState<Record<number, Guideline[]>>({})

  const [reviewerActions, setReviewerActions] =
    useState<ReviewerAction[]>([])

  const [submissionWorkspaceIds, setSubmissionWorkspaceIds] =
    useState<Record<number, number | null>>({})

  const [submissionCreatorIds, setSubmissionCreatorIds] =
    useState<Record<number, string>>({})

  const [approvalSources, setApprovalSources] =
    useState<Record<number, ApprovalSource>>({})

  const [publishedSubmissionIds, setPublishedSubmissionIds] =
    useState<number[]>([])

  const [selectedInsightWorkspaceId, setSelectedInsightWorkspaceId] =
    useState<number | null>(null)

  const [archiveExpanded, setArchiveExpanded] =
    useState(true)

  // ==========================================
  // REVIEW QUEUE
  // ==========================================

  const [submissions, setSubmissions] =
    useState<ReviewSubmission[]>([])

  const [selectedSubmission, setSelectedSubmission] =
    useState<ReviewSubmission | null>(null)

  const [changeRequestComment, setChangeRequestComment] =
    useState('')

  const [showChangeRequestModal, setShowChangeRequestModal] =
    useState(false)

  // ==========================================
  // SETTINGS
  // ==========================================

  const [settingsSection, setSettingsSection] =
    useState('profile')

  // ==========================================
  // CURRENT ROLE
  // ==========================================

  const activeWorkspace = workspaces.find(
    (workspace) => workspace.id === activeWorkspaceId
  )

  const currentWorkspaceRole:
    | 'Creator'
    | 'Reviewer'
    | 'Brand Manager' =
    selectedPurpose === 'Business'
      ? 'Brand Manager'
      : activeWorkspace?.members.find(
          (member) => member.userId === userId
        )?.role ?? 'Creator'

  // ==========================================
  // LOCAL DEMO STORAGE
  // ==========================================

  // Workspaces and assignments persist in this browser so the Brand Manager
  // does not lose them when navigating or refreshing the demo.
  const loadDemoData = () => {
    try {
      const savedWorkspaces = localStorage.getItem('engano_workspaces')
      const savedAssignments = localStorage.getItem('engano_assignments')
      const savedGuidelines = localStorage.getItem('engano_workspace_guidelines')
      const savedReviewerActions = localStorage.getItem('engano_reviewer_actions')
      const savedSubmissionWorkspaceIds = localStorage.getItem('engano_submission_workspace_ids')
      const savedSubmissionCreatorIds = localStorage.getItem('engano_submission_creator_ids')
      const savedSubmissions = localStorage.getItem('engano_submissions')
      const savedCreatorHistory = localStorage.getItem('engano_creator_history')
      const savedApprovalSources = localStorage.getItem('engano_approval_sources')
      const savedPublishedSubmissions = localStorage.getItem('engano_published_submissions')

      if (savedWorkspaces) {
        setWorkspaces(JSON.parse(savedWorkspaces) as Workspace[])
      }

      if (savedAssignments) {
        setWorkspaceAssignments(
          JSON.parse(savedAssignments) as WorkspaceAssignment[]
        )
      }

      if (savedGuidelines) {
        setWorkspaceGuidelinesState(
          JSON.parse(savedGuidelines) as Record<number, Guideline[]>
        )
      }

      if (savedReviewerActions) {
        setReviewerActions(
          JSON.parse(savedReviewerActions) as ReviewerAction[]
        )
      }

      if (savedSubmissionWorkspaceIds) {
        setSubmissionWorkspaceIds(
          JSON.parse(savedSubmissionWorkspaceIds) as Record<number, number | null>
        )
      }

      if (savedSubmissionCreatorIds) {
        setSubmissionCreatorIds(JSON.parse(savedSubmissionCreatorIds) as Record<number, string>)
      }
      if (savedSubmissions) {
        setSubmissions(JSON.parse(savedSubmissions) as ReviewSubmission[])
      }
      if (savedCreatorHistory) {
        setCreatorHistory(JSON.parse(savedCreatorHistory) as CreatorHistoryItem[])
      }

      if (savedApprovalSources) {
        setApprovalSources(
          JSON.parse(savedApprovalSources) as Record<number, ApprovalSource>
        )
      }

      if (savedPublishedSubmissions) {
        setPublishedSubmissionIds(
          JSON.parse(savedPublishedSubmissions) as number[]
        )
      }
    } catch (error) {
      console.error('Could not load ENGANO demo data', error)
    }
  }

  const saveWorkspaces = (nextWorkspaces: Workspace[]) => {
    setWorkspaces(nextWorkspaces)
    try {
      localStorage.setItem('engano_workspaces', JSON.stringify(nextWorkspaces))
    } catch (error) {
      console.error('Could not save ENGANO workspaces', error)
    }
  }

  const saveAssignments = (nextAssignments: WorkspaceAssignment[]) => {
    setWorkspaceAssignments(nextAssignments)
    try {
      localStorage.setItem('engano_assignments', JSON.stringify(nextAssignments))
    } catch (error) {
      console.error('Could not save ENGANO assignments', error)
    }
  }

  const saveReviewerActions = (nextActions: ReviewerAction[]) => {
    setReviewerActions(nextActions)
    try {
      localStorage.setItem('engano_reviewer_actions', JSON.stringify(nextActions))
    } catch (error) {
      console.error('Could not save reviewer actions', error)
    }
  }

  const saveSubmissionWorkspaceIds = (nextIds: Record<number, number | null>) => {
    setSubmissionWorkspaceIds(nextIds)
    try {
      localStorage.setItem('engano_submission_workspace_ids', JSON.stringify(nextIds))
    } catch (error) {
      console.error('Could not save submission workspace mapping', error)
    }
  }

  const saveSubmissions = (nextSubmissions: ReviewSubmission[]) => {
    setSubmissions(nextSubmissions)
    localStorage.setItem('engano_submissions', JSON.stringify(nextSubmissions))
  }

  const saveSubmissionCreatorIds = (nextIds: Record<number, string>) => {
    setSubmissionCreatorIds(nextIds)
    localStorage.setItem('engano_submission_creator_ids', JSON.stringify(nextIds))
  }

  const saveCreatorHistory = (nextHistory: CreatorHistoryItem[]) => {
    setCreatorHistory(nextHistory)
    localStorage.setItem('engano_creator_history', JSON.stringify(nextHistory))
  }

  const saveApprovalSources = (nextSources: Record<number, ApprovalSource>) => {
    setApprovalSources(nextSources)
    try {
      localStorage.setItem('engano_approval_sources', JSON.stringify(nextSources))
    } catch (error) {
      console.error('Could not save approval sources', error)
    }
  }

  const savePublishedSubmissionIds = (nextIds: number[]) => {
    setPublishedSubmissionIds(nextIds)
    try {
      localStorage.setItem('engano_published_submissions', JSON.stringify(nextIds))
    } catch (error) {
      console.error('Could not save published submissions', error)
    }
  }

  const updateGuidelinesForWorkspace: Dispatch<SetStateAction<Guideline[]>> = (value) => {
    setGuidelines((current) => {
      const next = typeof value === 'function' ? value(current) : value
      if (activeWorkspaceId !== null) {
        setWorkspaceGuidelinesState((currentMap) => {
          const nextMap = { ...currentMap, [activeWorkspaceId]: next }
          try {
            localStorage.setItem('engano_workspace_guidelines', JSON.stringify(nextMap))
          } catch (error) {
            console.error('Could not save workspace guidelines', error)
          }
          return nextMap
        })
      }
      return next
    })
  }

  // ==========================================
  // LOGIN
  // ==========================================

  const handleLogin = (event: FormEvent) => {
    event.preventDefault()

    if (
      userId.trim() === '' ||
      email.trim() === '' ||
      password.trim() === ''
    ) {
      return
    }

    loadDemoData()
    setIsLoggedIn(true)
    setPurposeConfirmed(false)
    setSelectedPurpose(null)
    setActivePage('studio')
  }

  // ==========================================
  // LOGOUT
  // ==========================================

  const handleLogout = () => {
    setIsLoggedIn(false)

    setPurposeConfirmed(false)
    setSelectedPurpose(null)

    setPassword('')
    setShowPassword(false)

    setActivePage('studio')

    setWorkspaceJoined(false)
    setActiveWorkspaceId(null)
    setWorkspaceCodeInput('')
    setWorkspaceMessage('')
    setShowJoinWorkspaceModal(false)

    setSettingsSection('profile')
  }

  // ==========================================
  // WORKSPACE CODE GENERATOR
  // ==========================================

  const generateWorkspaceCode = () => {
    const characters =
      'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'

    let code = 'ENG-'

    for (let index = 0; index < 6; index += 1) {
      code +=
        characters[
          Math.floor(
            Math.random() * characters.length
          )
        ]
    }

    return code
  }

  // ==========================================
  // CREATE WORKSPACE
  // ==========================================

  const createWorkspace = () => {
    const trimmedName = workspaceName.trim()

    if (trimmedName === '') {
      setWorkspaceMessage('Enter a workspace name first.')
      return
    }

    const newWorkspace: Workspace = {
      id: Date.now(),
      name: trimmedName,
      code: generateWorkspaceCode(),
      createdAt: new Date().toLocaleDateString(),
      createdBy: userId,
      members: [],
    }

    saveWorkspaces([newWorkspace, ...workspaces])
    setWorkspaceGuidelinesState((current) => ({ ...current, [newWorkspace.id]: [] }))
    try {
      localStorage.setItem(
        'engano_workspace_guidelines',
        JSON.stringify({ ...workspaceGuidelines, [newWorkspace.id]: [] })
      )
    } catch (error) {
      console.error('Could not save workspace guidelines', error)
    }
    setGuidelines([])
    setActiveWorkspaceId(newWorkspace.id)
    setWorkspaceName('')
    setWorkspaceCode(newWorkspace.code)
    setWorkspaceMembers([])
    setWorkspaceMessage(
      'Workspace created successfully. Share the generated code with your creators.'
    )
  }

  const deleteWorkspace = (workspaceId: number) => {
    const workspace = workspaces.find((item) => item.id === workspaceId)
    if (!workspace) return
    if (!window.confirm(`Delete workspace "${workspace.name}"? Its assignments, guidelines, and demo review data will also be removed.`)) return
    const nextWorkspaces = workspaces.filter((item) => item.id !== workspaceId)
    const nextAssignments = workspaceAssignments.filter((item) => item.workspaceId !== workspaceId)
    const nextGuidelines = { ...workspaceGuidelines }
    delete nextGuidelines[workspaceId]
    const removedIds = new Set(Object.entries(submissionWorkspaceIds).filter(([, id]) => id === workspaceId).map(([id]) => Number(id)))
    const nextSubmissions = submissions.filter((submission) => !removedIds.has(submission.id))
    const nextWorkspaceIds = { ...submissionWorkspaceIds }
    const nextCreatorIds = { ...submissionCreatorIds }
    const nextSources = { ...approvalSources }
    removedIds.forEach((id) => { delete nextWorkspaceIds[id]; delete nextCreatorIds[id]; delete nextSources[id] })
    saveWorkspaces(nextWorkspaces)
    saveAssignments(nextAssignments)
    saveSubmissions(nextSubmissions)
    saveSubmissionWorkspaceIds(nextWorkspaceIds)
    saveSubmissionCreatorIds(nextCreatorIds)
    saveApprovalSources(nextSources)
    savePublishedSubmissionIds(publishedSubmissionIds.filter((id) => !removedIds.has(id)))
    saveReviewerActions(reviewerActions.filter((action) => action.workspaceId !== workspaceId))
    setWorkspaceGuidelinesState(nextGuidelines)
    localStorage.setItem('engano_workspace_guidelines', JSON.stringify(nextGuidelines))
    if (activeWorkspaceId === workspaceId) { setActiveWorkspaceId(null); setWorkspaceMembers([]); setWorkspaceCode(''); setWorkspaceName('') }
    setWorkspaceMessage(`Workspace "${workspace.name}" deleted.`)
    setActivePage('workspace')
  }

  const openWorkspace = (workspace: Workspace) => {
    setActiveWorkspaceId(workspace.id)
    setWorkspaceCode(workspace.code)
    setWorkspaceName(workspace.name)
    setWorkspaceMembers(workspace.members)
    setGuidelines(workspaceGuidelines[workspace.id] ?? [])
    setSelectedInsightWorkspaceId(workspace.id)
    setWorkspaceMessage('')
    setActivePage('workspace')
  }

  const createAssignment = () => {
    if (!activeWorkspaceId || !assignmentTitle.trim() || !assignmentDueDate) {
      setWorkspaceMessage('Enter an assignment title and due date first.')
      return
    }

    const assignment: WorkspaceAssignment = {
      id: Date.now(),
      workspaceId: activeWorkspaceId,
      title: assignmentTitle.trim(),
      description: assignmentDescription.trim(),
      dueDate: assignmentDueDate,
      createdAt: new Date().toLocaleDateString(),
    }

    saveAssignments([assignment, ...workspaceAssignments])
    setAssignmentTitle('')
    setAssignmentDescription('')
    setAssignmentDueDate('')
    setWorkspaceMessage('Assignment published successfully for this workspace.')
  }

  // ==========================================
  // JOIN WORKSPACE
  // ==========================================

  const joinWorkspace = () => {
    const enteredCode = workspaceCodeInput.trim().toUpperCase()

    if (enteredCode === '') {
      setWorkspaceMessage('Enter a workspace code.')
      return
    }

    const workspace = workspaces.find(
      (item) => item.code.toUpperCase() === enteredCode
    )

    if (!workspace) {
      setWorkspaceMessage(
        'Invalid workspace code. Ask your Brand Manager for the correct code.'
      )
      return
    }

    const alreadyMember = workspace.members.some(
      (member) => member.userId === userId
    )

    const nextWorkspace = alreadyMember
      ? workspace
      : {
          ...workspace,
          members: [
            ...workspace.members,
            { id: Date.now(), userId, role: 'Creator' as const },
          ],
        }

    const nextWorkspaces = workspaces.map((item) =>
      item.id === workspace.id ? nextWorkspace : item
    )

    saveWorkspaces(nextWorkspaces)
    setActiveWorkspaceId(workspace.id)
    setWorkspaceMembers(nextWorkspace.members)
    setWorkspaceJoined(true)
    setWorkspaceCode(workspace.code)
    setWorkspaceName(workspace.name)
    setGuidelines(workspaceGuidelines[workspace.id] ?? [])
    setSelectedInsightWorkspaceId(workspace.id)
    setWorkspaceCodeInput('')
    setWorkspaceMessage(`You joined ${workspace.name} successfully.`)
    setShowJoinWorkspaceModal(false)
  }

  // ==========================================
  // LEAVE WORKSPACE
  // ==========================================

  const leaveWorkspace = () => {
    if (!activeWorkspaceId) return

    const workspace = workspaces.find((item) => item.id === activeWorkspaceId)
    if (!workspace) return

    const nextMembers = workspace.members.filter((member) => member.userId !== userId)
    const nextWorkspaces = workspaces.map((item) =>
      item.id === activeWorkspaceId ? { ...item, members: nextMembers } : item
    )

    saveWorkspaces(nextWorkspaces)
    setWorkspaceMembers([])
    setActiveWorkspaceId(null)
    setWorkspaceJoined(false)
    setWorkspaceCode('')
    setWorkspaceName('')
    setGuidelines([])
    setActivePage('studio')
    setWorkspaceMessage('You left the workspace. You can join again with a workspace code.')
  }

  // ==========================================
  // ASSIGN REVIEWER
  // ==========================================

  const assignReviewer = () => {
    if (selectedReviewerId === null || !activeWorkspaceId) {
      return
    }

    const nextMembers = workspaceMembers.map((member) => ({
      ...member,
      role: member.id === selectedReviewerId ? ('Reviewer' as const) : member.role,
    }))

    const nextWorkspaces = workspaces.map((workspace) =>
      workspace.id === activeWorkspaceId
        ? { ...workspace, members: nextMembers }
        : workspace
    )

    saveWorkspaces(nextWorkspaces)
    setWorkspaceMembers(nextMembers)
    setSelectedReviewerId(null)
    setWorkspaceMessage('Reviewer assigned successfully.')
  }

  // ==========================================
  // CREATOR CONTENT IMPROVEMENT
  // ==========================================

  const improveCreatorContent = async () => {
    if (!creatorDraft.trim()) {
      return
    }

    setIsCreatorImproving(true)
    setCreatorMessage('')

    const apiUrl =
      typeof import.meta.env.VITE_AI_API_URL === 'string'
        ? import.meta.env.VITE_AI_API_URL.replace(/\/$/, '')
        : ''

    try {
      // Backend contract:
      // POST {VITE_AI_API_URL}/creator/improve
      // body: { content, platform, autoSpelling, autoGrammar }
      // response: { improvedContent, suggestions?: string[] }
      if (apiUrl) {
        const response = await fetch(
          `${apiUrl}/creator/improve`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              content: creatorDraft.trim(),
              platform: creatorPlatform,
              autoSpelling,
              autoGrammar,
            }),
          }
        )

        if (!response.ok) {
          throw new Error('AI service request failed')
        }

        const data = (await response.json()) as {
          improvedContent?: string
          suggestions?: string[]
        }

        if (!data.improvedContent) {
          throw new Error('AI service returned no improved content')
        }

        setCreatorImproved(data.improvedContent)
        setCreatorMessage(
          data.suggestions?.length
            ? data.suggestions.join(' • ')
            : 'ENGANO AI improved your content for the selected platform.'
        )

        saveCreatorHistory([{ id: Date.now(), platform: creatorPlatform, input: creatorDraft.trim(), output: data.improvedContent as string, createdAt: new Date().toLocaleString() }, ...creatorHistory])

        return
      }

      // Local demo fallback until the backend URL is connected.
      let improved = creatorDraft
        .replace(/\s+/g, ' ')
        .trim()

      if (autoSpelling) {
        improved = improved
          .replace(/\bteh\b/gi, 'the')
          .replace(/\badn\b/gi, 'and')
          .replace(/\byoure\b/gi, "you're")
          .replace(/\brecieve\b/gi, 'receive')
          .replace(/\bseperate\b/gi, 'separate')
      }

      if (autoGrammar) {
        improved = improved.replace(
          /(^|[.!?]\s+)([a-z])/g,
          (_, prefix, letter) =>
            `${prefix}${letter.toUpperCase()}`
        )

        if (
          improved.length > 0 &&
          !/[.!?]$/.test(improved)
        ) {
          improved += '.'
        }
      }

      const platformGuidance: Record<string, string> = {
        Instagram:
          'Make it concise, engaging, visually readable, and suitable for a social caption.',
        WhatsApp:
          'Keep it conversational, clear, short, and easy to scan in a chat.',
        Discord:
          'Keep it community-friendly, direct, and structured for a Discord channel.',
        Gmail:
          'Use a professional tone, clear purpose, and an email-ready structure.',
      }

      improved = `${improved}\n\n[${creatorPlatform} guidance]\n${platformGuidance[creatorPlatform]}`

      setCreatorImproved(improved)
      setCreatorMessage(
        'Demo mode: VITE_AI_API_URL is not configured, so ENGANO used the local assistant fallback.'
      )

      saveCreatorHistory([{ id: Date.now(), platform: creatorPlatform, input: creatorDraft.trim(), output: improved, createdAt: new Date().toLocaleString() }, ...creatorHistory])
    } catch (error) {
      console.error(error)
      setCreatorMessage(
        'The AI service could not be reached. Check the backend URL and try again.'
      )
    } finally {
      setIsCreatorImproving(false)
    }
  }

  // ==========================================
  // RUN ENGANO REVIEW
  // ==========================================

  const runReview = async () => {
    if (!content.trim()) {
      return
    }

    setIsReviewing(true)
    setAiConfidence(null)
    setNeedsHumanReview(false)

    const apiUrl =
      typeof import.meta.env.VITE_AI_API_URL === 'string'
        ? import.meta.env.VITE_AI_API_URL.replace(/\/$/, '')
        : ''

    try {
      // Backend contract:
      // POST {VITE_AI_API_URL}/review
      // body: { content, title, guidelines }
      // response: { findings, confidence, needsHumanReview }
      if (apiUrl) {
        const response = await fetch(
          `${apiUrl}/review`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              content: content.trim(),
              title: draftTitle.trim(),
              guidelines,
            }),
          }
        )

        if (!response.ok) {
          throw new Error('AI review request failed')
        }

        const data = (await response.json()) as {
          findings?: Finding[]
          confidence?: number
          needsHumanReview?: boolean
        }

        const backendFindings = data.findings ?? []
        const confidence =
          typeof data.confidence === 'number'
            ? data.confidence
            : backendFindings.some(
                  (finding) =>
                    finding.severity === 'Critical'
                )
              ? 55
              : 92

        const humanReview =
          typeof data.needsHumanReview === 'boolean'
            ? data.needsHumanReview
            : confidence < 80

        setFindings(backendFindings)
        setAiConfidence(confidence)
        setNeedsHumanReview(humanReview)
        setIsReviewing(false)
        return
      }

      // Local demo fallback.
      const newFindings: Finding[] = []
      const lowerContent = content.toLowerCase()

      if (
        lowerContent.includes('fastest') ||
        lowerContent.includes('best in the world') ||
        lowerContent.includes('#1')
      ) {
        newFindings.push({
          severity: 'Critical',
          category: 'Unsupported Claim',
          issue: 'Potential unsupported promotional claim',
          explanation:
            'The content contains a strong promotional claim that may require an approved source or benchmark.',
          guideline:
            'Avoid superlative claims unless they are supported by an approved source.',
          suggestion:
            'Replace the claim with a factual statement that can be verified.',
        })
      }

      if (
        lowerContent.includes('free forever') ||
        lowerContent.includes('100% free')
      ) {
        newFindings.push({
          severity: 'Warning',
          category: 'Promotional Language',
          issue: 'Potentially misleading promotional wording',
          explanation:
            'This wording may create a stronger promise than the approved product information supports.',
          guideline:
            'Do not make promotional promises that are not present in the approved product information.',
          suggestion:
            'Use the exact approved pricing or offer language instead.',
        })
      }

      if (
        lowerContent.includes('nimbusdb') ||
        lowerContent.includes('nimbus database')
      ) {
        newFindings.push({
          severity: 'Warning',
          category: 'Terminology',
          issue: 'Non-approved product terminology',
          explanation:
            'The product name does not match the preferred terminology stored in the Brand Library.',
          guideline:
            'Use the approved product name: "Nimbus DB".',
          suggestion:
            'Replace the incorrect product name with "Nimbus DB".',
        })
      }

      if (
        lowerContent.includes('guaranteed') ||
        lowerContent.includes('guarantee')
      ) {
        newFindings.push({
          severity: 'Warning',
          category: 'Claims',
          issue: 'Guarantee language detected',
          explanation:
            'Guarantee-based language can create a claim that requires explicit approval or supporting evidence.',
          guideline:
            'Avoid guarantees unless they are explicitly approved.',
          suggestion:
            'Rewrite the statement as a factual product capability.',
        })
      }

      guidelines.forEach((guideline) => {
        const guidelineWords = guideline.text
          .toLowerCase()
          .replace(/[.,!?\'"()]/g, '')
          .split(/\s+/)
          .filter((word) => word.length > 3)

        if (guideline.type === "DON'T") {
          const matchedWord = guidelineWords.find((word) =>
            lowerContent.includes(word)
          )

          if (matchedWord) {
            newFindings.push({
              severity: 'Warning',
              category: 'Brand Guideline',
              issue: 'Brand guideline may be violated',
              explanation: `The content contains "${matchedWord}", which may conflict with a rule configured in the Brand Library.`,
              guideline: guideline.text,
              suggestion:
                'Review this statement and rewrite it to comply with the configured brand guideline.',
            })
          }
        }
      })

      if (newFindings.length === 0) {
        newFindings.push({
          severity: 'Suggestion',
          category: 'Brand Check',
          issue: 'No major issues detected',
          explanation:
            'ENGANO did not detect any currently configured demonstration rules or brand guideline conflicts.',
          guideline:
            'Continue following the approved brand guidelines and source material.',
          suggestion:
            'AI confidence is high. The draft can move toward Brand Manager approval.',
        })
      }

      const confidence = newFindings.some(
        (finding) => finding.severity === 'Critical'
      )
        ? 55
        : newFindings.some(
              (finding) => finding.severity === 'Warning'
            )
          ? 72
          : 94

      setFindings(newFindings)
      setAiConfidence(confidence)
      setNeedsHumanReview(confidence < 80)
    } catch (error) {
      console.error(error)
      setCreatorMessage(
        'The AI review service could not be reached. The draft was not submitted.'
      )
    } finally {
      setIsReviewing(false)
    }
  }

  // ==========================================
  // CREATE NEW DRAFT
  // ==========================================

  const createNewDraft = () => {
    setEditingSubmissionId(null)
    setDraftTitle('')
    setContent('')
    setFindings([])
    setAiConfidence(null)
    setNeedsHumanReview(false)
    setIsCreatingDraft(true)
    setActivePage('drafts')
  }

  // ==========================================
  // CANCEL DRAFT
  // ==========================================

  const cancelDraft = () => {
    setEditingSubmissionId(null)
    setIsCreatingDraft(false)
    setDraftTitle('')
    setContent('')
    setFindings([])
    setAiConfidence(null)
    setNeedsHumanReview(false)
  }

  // ==========================================
  // SUBMIT FOR REVIEW
  // ==========================================

  const submitForReview = () => {
    if (!content.trim()) return

    const workspaceId = workspaceJoined ? activeWorkspaceId : null
    const status: ReviewSubmission['status'] = workspaceJoined && !needsHumanReview ? 'Approved' : 'Pending Review'
    const source: ApprovalSource | null = workspaceJoined && !needsHumanReview ? 'AI' : null

    if (editingSubmissionId !== null) {
      saveSubmissions(submissions.map((submission) => submission.id === editingSubmissionId ? { ...submission, title: draftTitle.trim() || 'Untitled Draft', content: content.trim(), findings, status, submittedAt: 'just now', reviewerComment: undefined } : submission))
      saveSubmissionCreatorIds({ ...submissionCreatorIds, [editingSubmissionId]: submissionCreatorIds[editingSubmissionId] ?? userId })
      const nextSources = { ...approvalSources }
      if (source) nextSources[editingSubmissionId] = source
      else delete nextSources[editingSubmissionId]
      saveApprovalSources(nextSources)
      saveCreatorHistory([{ id: Date.now(), platform: creatorPlatform, input: content.trim(), output: content.trim(), createdAt: new Date().toLocaleString() }, ...creatorHistory])
      setEditingSubmissionId(null)
    } else {
      const submission: ReviewSubmission = { id: Date.now(), title: draftTitle.trim() || 'Untitled Draft', content: content.trim(), findings, status, submittedAt: 'just now' }
      saveSubmissions([submission, ...submissions])
      saveSubmissionCreatorIds({ ...submissionCreatorIds, [submission.id]: userId })
      saveSubmissionWorkspaceIds({ ...submissionWorkspaceIds, [submission.id]: workspaceId })
      if (source) saveApprovalSources({ ...approvalSources, [submission.id]: source })
      saveCreatorHistory([{ id: Date.now() + 1, platform: creatorPlatform, input: content.trim(), output: content.trim(), createdAt: new Date().toLocaleString() }, ...creatorHistory])
    }

    setIsCreatingDraft(false)
    setDraftTitle('')
    setContent('')
    setFindings([])
    setAiConfidence(null)
    setNeedsHumanReview(false)
    setActivePage(workspaceJoined ? (needsHumanReview ? 'drafts' : 'approvals') : 'history')
  }

  const editCreatorSubmission = (submission: ReviewSubmission) => {
    setEditingSubmissionId(submission.id)
    setDraftTitle(submission.title)
    setContent(submission.content)
    setFindings(submission.findings)
    setAiConfidence(null)
    setNeedsHumanReview(false)
    setIsCreatingDraft(true)
    setActivePage('drafts')
  }

  // ==========================================
  // OPEN SUBMISSION
  // ==========================================

  const openSubmission = (
    submission: ReviewSubmission
  ) => {
    setSelectedSubmission(
      submission
    )

    setActivePage(
      'reviewDetail'
    )
  }

  // ==========================================
  // APPROVE SUBMISSION
  // ==========================================

  const approveSubmission = () => {
    if (
      !selectedSubmission
    ) {
      return
    }

    setSubmissions(
      (currentSubmissions) =>
        currentSubmissions.map(
          (submission) =>
            submission.id ===
            selectedSubmission.id
              ? {
                  ...submission,
                  status:
                    'Approved',
                }
              : submission
        )
    )

    setSelectedSubmission(null)
    setActivePage(
      'reviewQueue'
    )
  }

  // ==========================================
  // REQUEST CHANGES
  // ==========================================

  const requestChanges = () => {
    if (
      !selectedSubmission
    ) {
      return
    }

    if (
      changeRequestComment.trim() ===
      ''
    ) {
      return
    }

    setSubmissions(
      (currentSubmissions) =>
        currentSubmissions.map(
          (submission) =>
            submission.id ===
            selectedSubmission.id
              ? {
                  ...submission,
                  status:
                    'Changes Requested',
                  reviewerComment:
                    changeRequestComment.trim(),
                }
              : submission
        )
    )

    if (currentWorkspaceRole === 'Reviewer') {
      const workspaceId = submissionWorkspaceIds[selectedSubmission.id] ?? activeWorkspaceId
      const action: ReviewerAction = {
        id: Date.now(),
        submissionId: selectedSubmission.id,
        workspaceId,
        title: selectedSubmission.title,
        action: 'Request Changes',
        createdAt: 'just now',
      }
      saveReviewerActions([action, ...reviewerActions])
    }

    setChangeRequestComment('')
    setShowChangeRequestModal(false)
    setSelectedSubmission(null)
    setActivePage(
      'reviewQueue'
    )
  }

  const reviewerApproveSubmission = () => {
    if (!selectedSubmission) return

    const workspaceId = submissionWorkspaceIds[selectedSubmission.id] ?? activeWorkspaceId
    const action: ReviewerAction = {
      id: Date.now(),
      submissionId: selectedSubmission.id,
      workspaceId,
      title: selectedSubmission.title,
      action: 'Direct Approval',
      createdAt: 'just now',
    }

    setSubmissions((currentSubmissions) =>
      currentSubmissions.map((submission) =>
        submission.id === selectedSubmission.id
          ? { ...submission, status: 'Approved' }
          : submission
      )
    )

    saveReviewerActions([action, ...reviewerActions])
    saveApprovalSources({ ...approvalSources, [selectedSubmission.id]: 'Reviewer' })
    setSelectedSubmission(null)
    setActivePage('reviewQueue')
  }

  const publishSubmission = (submission: ReviewSubmission) => {
    savePublishedSubmissionIds([...publishedSubmissionIds, submission.id])
    saveApprovalSources({ ...approvalSources, [submission.id]: 'Brand Manager' })
    setWorkspaceMessage(`\"${submission.title}\" has been marked as published.`)
  }

  // ==========================================
  // LOGIN SCREEN
  // ==========================================

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-slate-950 text-white">
        <div className="flex min-h-screen items-center justify-center px-6">
          <div className="w-full max-w-md">

            <div className="mb-8 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-emerald-500 text-xl font-bold text-slate-950">
                E
              </div>

              <h1 className="mt-4 text-3xl font-bold tracking-tight">
                ENGANO
              </h1>

              <p className="mt-2 text-sm text-slate-400">
                AI-powered brand governance
              </p>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-2xl">

              <div className="mb-6">
                <h2 className="text-2xl font-semibold">
                  Welcome back
                </h2>

                <p className="mt-2 text-sm text-slate-400">
                  Sign in to continue to your ENGANO workspace.
                </p>
              </div>

              <form
                onSubmit={handleLogin}
                className="space-y-5"
              >

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-300">
                    User ID
                  </label>

                  <input
                    type="text"
                    value={userId}
                    onChange={(event) =>
                      setUserId(
                        event.target.value
                      )
                    }
                    placeholder="Enter your User ID"
                    autoComplete="username"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-emerald-500"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-300">
                    Email
                  </label>

                  <input
                    type="email"
                    value={email}
                    onChange={(event) =>
                      setEmail(
                        event.target.value
                      )
                    }
                    placeholder="you@example.com"
                    autoComplete="email"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-emerald-500"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-300">
                    Password
                  </label>

                  <div className="relative">
                    <input
                      type={
                        showPassword
                          ? 'text'
                          : 'password'
                      }
                      value={password}
                      onChange={(event) =>
                        setPassword(
                          event.target.value
                        )
                      }
                      placeholder="Enter your password"
                      autoComplete="current-password"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 pr-12 text-sm text-white outline-none placeholder:text-slate-600 focus:border-emerald-500"
                    />

                    <button
                      type="button"
                      onClick={() =>
                        setShowPassword(
                          (current) =>
                            !current
                        )
                      }
                      className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-500 hover:text-slate-200"
                    >
                      {showPassword ? (
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          className="h-5 w-5"
                        >
                          <path d="M3 3l18 18" />
                          <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                          <path d="M9.9 4.2A10.8 10.8 0 0 1 12 4c5 0 8.5 4 10 8-0.6 1.5-1.6 3-2.9 4.2" />
                          <path d="M6.6 6.6C4.8 7.7 3.6 9.4 2 12c1.5 4 5 8 10 8 1.3 0 2.5-.2 3.6-.7" />
                        </svg>
                      ) : (
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          className="h-5 w-5"
                        >
                          <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
                          <circle
                            cx="12"
                            cy="12"
                            r="3"
                          />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  className="w-full rounded-lg bg-emerald-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
                >
                  Sign In
                </button>

                <div className="flex items-center gap-3 py-1">
                  <div className="h-px flex-1 bg-slate-800" />
                  <span className="text-xs text-slate-500">
                    OR
                  </span>
                  <div className="h-px flex-1 bg-slate-800" />
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setUserId(
                      'google-user'
                    )
                    setEmail(
                      'google-user@example.com'
                    )
                    setPassword(
                      'demo-password'
                    )
                    loadDemoData()
                    setIsLoggedIn(true)
                    setPurposeConfirmed(
                      false
                    )
                    setSelectedPurpose(
                      null
                    )
                  }}
                  className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-700 bg-slate-950 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800"
                >
                  <svg
                    viewBox="0 0 24 24"
                    className="h-5 w-5"
                  >
                    <path
                      fill="#4285F4"
                      d="M21.35 12.23c0-.68-.06-1.35-.18-1.98H12v3.75h5.24a4.48 4.48 0 0 1-1.94 2.94v2.45h3.14c1.84-1.69 2.91-4.18 2.91-7.16Z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 21.7c2.63 0 4.84-.87 6.45-2.36l-3.14-2.45c-.87.58-1.98.92-3.31.92-2.54 0-4.69-1.72-5.46-4.03H3.3v2.53A9.74 9.74 0 0 0 12 21.7Z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M6.54 13.78A5.86 5.86 0 0 1 6.23 12c0-.62.11-1.23.31-1.78V7.69H3.3A9.72 9.72 0 0 0 2.25 12c0 1.57.38 3.05 1.05 4.31l3.24-2.53Z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 6.19c1.43 0 2.71.49 3.72 1.45l2.79-2.79C16.83 3.29 14.63 2.3 12 2.3a9.74 9.74 0 0 0-8.7 5.39l3.24 2.53C7.31 7.91 9.46 6.19 12 6.19Z"
                    />
                  </svg>

                  Continue with Google
                </button>

              </form>

              <p className="mt-6 text-center text-xs text-slate-500">
                Demo login — authentication will be connected to the backend later.
              </p>

            </div>
          </div>
        </div>
      </div>
    )
  }

  // ==========================================
  // PURPOSE SELECTION
  // ==========================================

  if (!purposeConfirmed) {
    return (
      <div className="min-h-screen bg-slate-950 text-white">
        <div className="flex min-h-screen items-center justify-center px-6">
          <div className="w-full max-w-4xl">

            <div className="mb-10 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-emerald-500 text-xl font-bold text-slate-950">
                E
              </div>

              <h1 className="mt-5 text-3xl font-bold">
                How will you use ENGANO?
              </h1>

              <p className="mt-2 text-sm text-slate-400">
                Choose the experience that fits how you create and manage content.
              </p>
            </div>

            <div className="mx-auto grid max-w-3xl gap-5 md:grid-cols-2">

              {/* CREATOR */}
              <button
                type="button"
                onClick={() =>
                  setSelectedPurpose(
                    'Content Creator'
                  )
                }
                className={`rounded-2xl border p-7 text-left transition ${
                  selectedPurpose ===
                  'Content Creator'
                    ? 'border-emerald-500 bg-emerald-500/10 ring-1 ring-emerald-500/40'
                    : 'border-slate-800 bg-slate-900/70 hover:border-slate-600'
                }`}
              >
                <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-purple-500/10 text-3xl">
                  ✍️
                </div>

                <h2 className="mt-5 text-xl font-semibold">
                  Content Creator
                </h2>

                <p className="mt-2 text-sm leading-6 text-slate-400">
                  Create, improve, and adapt content for different platforms and audiences.
                </p>

                <p className="mt-4 text-xs font-medium text-emerald-400">
                  AI writing • Grammar • Platform optimization
                </p>
              </button>

              {/* BUSINESS */}
              <button
                type="button"
                onClick={() =>
                  setSelectedPurpose(
                    'Business'
                  )
                }
                className={`rounded-2xl border p-7 text-left transition ${
                  selectedPurpose ===
                  'Business'
                    ? 'border-emerald-500 bg-emerald-500/10 ring-1 ring-emerald-500/40'
                    : 'border-slate-800 bg-slate-900/70 hover:border-slate-600'
                }`}
              >
                <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-emerald-500/10 text-3xl">
                  🏢
                </div>

                <h2 className="mt-5 text-xl font-semibold">
                  Business
                </h2>

                <p className="mt-2 text-sm leading-6 text-slate-400">
                  Create workspaces, manage brand guidelines, assign reviewers, and approve content.
                </p>

                <p className="mt-4 text-xs font-medium text-emerald-400">
                  Workspaces • Reviews • Approvals • Guidelines
                </p>
              </button>

            </div>

            <div className="mt-8 flex justify-center">
              <button
                type="button"
                disabled={
                  !selectedPurpose
                }
                onClick={() => {
                  if (
                    !selectedPurpose
                  ) {
                    return
                  }

                  setPurposeConfirmed(
                    true
                  )

                  setActivePage(
                    selectedPurpose ===
                      'Business'
                      ? 'workspace'
                      : 'studio'
                  )
                }}
                className="rounded-lg bg-emerald-500 px-8 py-3 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Continue
              </button>
            </div>

          </div>
        </div>
      </div>
    )
  }

  // ==========================================
  // CREATOR DASHBOARD
  // ==========================================

  if (
    selectedPurpose ===
      'Content Creator' &&
    currentWorkspaceRole ===
      'Creator'
  ) {
    const creatorNavItems = workspaceJoined
      ? [
          ['studio', 'Studio'],
          ['drafts', 'Drafts'],
          ['approvals', 'Approvals'],
          ['history', 'History'],
          ['insights', 'Insights'],
          ['settings', 'Settings'],
        ]
      : [
          ['studio', 'Studio'],
          ['history', 'History'],
          ['settings', 'Settings'],
        ]

    return (
      <div className="min-h-screen bg-slate-950 text-white">
        <header className="flex h-16 items-center justify-between border-b border-slate-800 px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500 font-bold text-slate-950">
              E
            </div>
            <span className="text-xl font-bold">ENGANO</span>
            <span className="rounded-full bg-purple-500/10 px-3 py-1 text-xs font-medium text-purple-300">
              Creator
            </span>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => {
                setWorkspaceMessage('')
                setShowJoinWorkspaceModal(true)
              }}
              className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-xs font-semibold text-emerald-400 hover:bg-emerald-500/20"
            >
              {workspaceJoined ? 'WORKSPACE JOINED' : 'JOIN WORKSPACE'}
            </button>

            <button
              type="button"
              onClick={() => setActivePage('settings')}
              className={`rounded-lg border px-3 py-2 text-sm ${
                activePage === 'settings'
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                  : 'border-slate-700 text-slate-300 hover:bg-slate-800'
              }`}
              aria-label="Open settings"
            >
              ⚙
            </button>

            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-sm font-semibold">
              {userId.trim().charAt(0).toUpperCase() || 'U'}
            </div>
          </div>
        </header>

        <div className="flex min-h-[calc(100vh-4rem)]">
          <aside className="w-60 border-r border-slate-800 bg-slate-950 p-4">
            <p className="mb-4 px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
              {workspaceJoined ? 'Workspace Creator' : 'Creator Workspace'}
            </p>

            <nav className="space-y-1">
              {creatorNavItems.map(([page, label]) => (
                <button
                  key={page}
                  type="button"
                  onClick={() => setActivePage(page)}
                  className={`w-full rounded-lg px-3 py-2.5 text-left text-sm font-medium ${
                    activePage === page
                      ? 'bg-slate-800 text-white'
                      : 'text-slate-400 hover:bg-slate-900 hover:text-white'
                  }`}
                >
                  {label}
                </button>
              ))}
            </nav>

            {!workspaceJoined && (
              <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Solo Creator
                </p>
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  Join a workspace when you want brand review, approvals, and governance features.
                </p>
              </div>
            )}
          </aside>

          <main className="flex-1 p-8">
            {/* SOLO / CREATOR STUDIO */}
            {activePage === 'studio' && (
              <div className="mx-auto max-w-5xl">
                <div className="mb-8">
                  <p className="text-sm font-medium text-emerald-400">
                    {workspaceJoined ? 'Creator Studio' : 'Writing Assistant'}
                  </p>
                  <h1 className="mt-2 text-3xl font-semibold tracking-tight">
                    {workspaceJoined
                      ? 'Create and prepare content'
                      : 'Create better content with ENGANO'}
                  </h1>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                    Choose a platform and let ENGANO suggest changes for the way your audience reads content there.
                  </p>
                </div>

                <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <h2 className="text-xl font-semibold">Content Assistant</h2>
                      <p className="mt-1 text-sm text-slate-400">
                        AI suggestions are platform-aware for Instagram, WhatsApp, Discord, and Gmail.
                      </p>
                    </div>

                    <select
                      value={creatorPlatform}
                      onChange={(event) => {
                        setCreatorPlatform(event.target.value)
                        setCreatorImproved('')
                        setCreatorMessage('')
                      }}
                      className="rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-emerald-500"
                    >
                      <option>Instagram</option>
                      <option>WhatsApp</option>
                      <option>Discord</option>
                      <option>Gmail</option>
                    </select>
                  </div>

                  <textarea
                    rows={11}
                    value={creatorDraft}
                    onChange={(event) => {
                      setCreatorDraft(event.target.value)
                      setCreatorMessage('')
                    }}
                    placeholder={`Write your ${creatorPlatform} content here...`}
                    className="mt-5 w-full resize-none rounded-xl border border-slate-700 bg-slate-950 px-4 py-4 text-sm leading-6 text-white outline-none placeholder:text-slate-600 focus:border-emerald-500"
                  />

                  <div className="mt-4 flex gap-3">
                    <button
                      type="button"
                      onClick={improveCreatorContent}
                      disabled={!creatorDraft.trim() || isCreatorImproving}
                      className="rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {isCreatorImproving ? 'Asking ENGANO AI...' : 'Improve Content'}
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setCreatorDraft('')
                        setCreatorImproved('')
                        setCreatorMessage('')
                      }}
                      className="rounded-lg border border-slate-700 px-5 py-2.5 text-sm font-medium text-slate-300 hover:bg-slate-800"
                    >
                      Clear
                    </button>
                  </div>

                  {creatorMessage && (
                    <p className="mt-4 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3 text-sm leading-6 text-emerald-300">
                      {creatorMessage}
                    </p>
                  )}

                  {creatorImproved && (
                    <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/70 p-5">
                      <div className="flex items-center justify-between gap-3">
                        <h3 className="text-sm font-semibold">AI Suggestions / Improved Content</h3>
                        <span className="rounded-full bg-purple-500/10 px-3 py-1 text-xs text-purple-300">
                          {creatorPlatform}
                        </span>
                      </div>
                      <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-300">
                        {creatorImproved}
                      </p>
                    </div>
                  )}
                </section>

                {workspaceJoined && (
                  <div className="mt-6 flex items-center justify-between rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-5">
                    <div>
                      <p className="text-sm font-semibold text-emerald-300">Workspace connected</p>
                      <p className="mt-1 text-xs text-slate-400">
                        Your drafts can now go through ENGANO review and the workspace approval flow.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={createNewDraft}
                      className="rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
                    >
                      Create Draft
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* JOINED CREATOR DRAFTS */}
            {workspaceJoined && activePage === 'drafts' && (
              <div className="mx-auto max-w-5xl">
                <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-emerald-400">Workspace</p>
                    <h1 className="mt-2 text-3xl font-semibold">Drafts</h1>
                    <p className="mt-2 text-sm leading-6 text-slate-400">
                      Create content, review ENGANO's findings, and route uncertain drafts to the assigned reviewer.
                    </p>
                  </div>

                  {!isCreatingDraft && (
                    <button
                      type="button"
                      onClick={createNewDraft}
                      className="rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
                    >
                      New Draft
                    </button>
                  )}
                </div>

                {!isCreatingDraft ? (
                  <div className="space-y-4">
                    {submissions.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center">
                        <p className="text-lg font-medium">No drafts yet</p>
                        <p className="mt-2 text-sm text-slate-500">
                          Create your first workspace draft and run ENGANO review.
                        </p>
                        <button
                          type="button"
                          onClick={createNewDraft}
                          className="mt-5 rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
                        >
                          Create Draft
                        </button>
                      </div>
                    ) : (
                      submissions.map((submission) => (
                        <div
                          key={submission.id}
                          className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <h2 className="font-semibold">{submission.title}</h2>
                              <p className="mt-1 text-xs text-slate-500">{submission.submittedAt}</p>
                            </div>
                            <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">
                              {submission.status}
                            </span>
                          </div>
                          <p className="mt-4 line-clamp-3 whitespace-pre-wrap text-sm leading-6 text-slate-400">
                            {submission.content}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                ) : (
                  <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                    <input
                      type="text"
                      value={draftTitle}
                      onChange={(event) => setDraftTitle(event.target.value)}
                      placeholder="Draft title"
                      className="mb-4 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none focus:border-emerald-500"
                    />

                    <textarea
                      rows={12}
                      value={content}
                      onChange={(event) => setContent(event.target.value)}
                      placeholder="Write or paste content for ENGANO review..."
                      className="w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm leading-6 text-white outline-none focus:border-emerald-500"
                    />

                    <div className="mt-4 flex flex-wrap justify-end gap-3">
                      <button
                        type="button"
                        onClick={cancelDraft}
                        className="rounded-lg border border-slate-700 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={runReview}
                        disabled={isReviewing || !content.trim()}
                        className="rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {isReviewing ? 'AI Reviewing...' : 'Run ENGANO AI Review'}
                      </button>
                    </div>

                    {aiConfidence !== null && (
                      <div className={`mt-5 rounded-xl border p-5 ${
                        needsHumanReview
                          ? 'border-yellow-500/20 bg-yellow-500/5'
                          : 'border-emerald-500/20 bg-emerald-500/5'
                      }`}>
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold">
                              AI confidence: {aiConfidence}%
                            </p>
                            <p className="mt-1 text-xs text-slate-400">
                              {needsHumanReview
                                ? 'AI is not confident enough. A human reviewer is required.'
                                : 'AI is confident enough for the draft to move to Brand Manager approval.'}
                            </p>
                          </div>
                          <span className={`rounded-full px-3 py-1 text-xs font-medium ${
                            needsHumanReview
                              ? 'bg-yellow-500/10 text-yellow-300'
                              : 'bg-emerald-500/10 text-emerald-300'
                          }`}>
                            {needsHumanReview ? 'Human Review Required' : 'AI Confident'}
                          </span>
                        </div>
                      </div>
                    )}

                    {findings.length > 0 && (
                      <div className="mt-6 space-y-4">
                        <div>
                          <h2 className="text-lg font-semibold">AI Findings & Suggestions</h2>
                          <p className="mt-1 text-sm text-slate-400">
                            These findings come from ENGANO's AI review service when connected, or the local demo rules otherwise.
                          </p>
                        </div>

                        {findings.map((finding, index) => (
                          <div
                            key={index}
                            className="rounded-xl border border-slate-800 bg-slate-950/70 p-5"
                          >
                            <div className="flex items-start gap-3">
                              <div className={`mt-1 h-3 w-3 shrink-0 rounded-full ${
                                finding.severity === 'Critical'
                                  ? 'bg-red-500'
                                  : finding.severity === 'Warning'
                                    ? 'bg-yellow-400'
                                    : 'bg-blue-400'
                              }`} />
                              <div>
                                <div className="flex flex-wrap items-center gap-2">
                                  <h3 className="font-semibold">{finding.issue}</h3>
                                  <span className="rounded-full bg-slate-800 px-2 py-1 text-xs text-slate-300">
                                    {finding.severity}
                                  </span>
                                </div>
                                <p className="mt-1 text-xs text-slate-500">{finding.category}</p>
                              </div>
                            </div>
                            <p className="mt-4 text-sm leading-6 text-slate-400">{finding.explanation}</p>
                            <p className="mt-3 text-sm text-emerald-400">{finding.suggestion}</p>
                          </div>
                        ))}

                        <div className="flex flex-wrap justify-end gap-3">
                          <button
                            type="button"
                            onClick={cancelDraft}
                            className="rounded-lg border border-slate-700 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800"
                          >
                            Discard
                          </button>
                          <button
                            type="button"
                            onClick={submitForReview}
                            className="rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
                          >
                            {needsHumanReview
                              ? 'Send to Review Queue'
                              : 'Send to Brand Manager'}
                          </button>
                        </div>
                      </div>
                    )}
                  </section>
                )}
              </div>
            )}

            {/* WORKSPACE ASSIGNMENTS FOR CREATOR */}
            {workspaceJoined && activePage === 'drafts' && activeWorkspace && (
              <div className="mx-auto mb-8 max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                <div className="mb-5">
                  <h2 className="text-xl font-semibold">Workspace Assignments</h2>
                  <p className="mt-1 text-sm text-slate-400">Write and submit content for topics assigned by your Brand Manager.</p>
                </div>
                <div className="space-y-3">
                  {workspaceAssignments.filter((assignment) => assignment.workspaceId === activeWorkspace.id).length === 0 ? (
                    <div className="rounded-xl border border-dashed border-slate-700 p-6 text-center text-sm text-slate-500">No assignments have been posted yet.</div>
                  ) : (
                    workspaceAssignments.filter((assignment) => assignment.workspaceId === activeWorkspace.id).map((assignment) => (
                      <button
                        key={assignment.id}
                        type="button"
                        onClick={() => {
                          setDraftTitle(assignment.title)
                          setContent('')
                          setFindings([])
                          setAiConfidence(null)
                          setNeedsHumanReview(false)
                          setIsCreatingDraft(true)
                        }}
                        className="w-full rounded-xl border border-slate-800 bg-slate-950/60 p-5 text-left hover:border-emerald-500/40"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <h3 className="font-semibold text-white">{assignment.title}</h3>
                            {assignment.description && <p className="mt-2 text-sm leading-6 text-slate-400">{assignment.description}</p>}
                          </div>
                          <span className="rounded-full bg-yellow-500/10 px-3 py-1 text-xs text-yellow-300">Due {assignment.dueDate}</span>
                        </div>
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* CREATOR APPROVALS */}
            {workspaceJoined && activePage === 'approvals' && (
              <div className="mx-auto max-w-5xl">
                <div className="mb-8">
                  <p className="text-sm font-medium text-emerald-400">My submissions</p>
                  <h1 className="mt-2 text-3xl font-semibold">Approvals</h1>
                  <p className="mt-2 text-sm text-slate-400">See which drafts were approved and which need changes.</p>
                </div>
                <div className="mb-6 flex flex-wrap gap-2">
                  {(['All', 'Request Changes', 'Approved'] as const).map((filter) => (
                    <button key={filter} type="button" onClick={() => setApprovalFilter(filter)} className={`rounded-lg px-4 py-2 text-sm ${approvalFilter === filter ? 'bg-emerald-500 text-slate-950' : 'border border-slate-700 text-slate-300 hover:bg-slate-800'}`}>
                      {filter}
                    </button>
                  ))}
                </div>
                {(() => {
                  const mySubmissions = submissions.filter((submission) => {
                    const belongsToMe = submissionCreatorIds[submission.id] === userId
                    const inWorkspace = submissionWorkspaceIds[submission.id] === activeWorkspaceId
                    const matchesFilter = approvalFilter === 'All' || (approvalFilter === 'Request Changes' && submission.status === 'Changes Requested') || (approvalFilter === 'Approved' && submission.status === 'Approved')
                    return belongsToMe && inWorkspace && matchesFilter
                  })
                  return mySubmissions.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center">
                      <p className="text-lg font-medium">No matching submissions</p>
                      <p className="mt-2 text-sm text-slate-500">Your reviewed content will appear here.</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {mySubmissions.map((submission) => (
                        <div key={submission.id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                          <div className="flex flex-wrap items-start justify-between gap-4">
                            <div><h2 className="text-lg font-semibold">{submission.title}</h2><p className="mt-1 text-xs text-slate-500">Submitted {submission.submittedAt}</p></div>
                            <span className={`rounded-full px-3 py-1 text-xs ${submission.status === 'Changes Requested' ? 'bg-red-500/10 text-red-300' : 'bg-emerald-500/10 text-emerald-300'}`}>{submission.status}</span>
                          </div>
                          <p className="mt-5 whitespace-pre-wrap rounded-xl bg-slate-950/70 p-5 text-sm leading-7 text-slate-300">{submission.content}</p>
                          {submission.status === 'Changes Requested' && (
                            <div className="mt-5 rounded-xl border border-red-500/20 bg-red-500/5 p-5">
                              <p className="text-xs uppercase tracking-wider text-red-300">Reviewer feedback</p>
                              <p className="mt-2 text-sm leading-6 text-slate-300">{submission.reviewerComment || 'Changes were requested.'}</p>
                              <button type="button" onClick={() => editCreatorSubmission(submission)} className="mt-4 rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400">Edit & Resubmit</button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )
                })()}
              </div>
            )}

            {/* CREATOR HISTORY */}
            {activePage === 'history' && (
              <div className="mx-auto max-w-5xl">
                <div className="mb-8"><h1 className="text-3xl font-semibold">History</h1><p className="mt-2 text-sm text-slate-400">All your writing-assistant sessions and workspace drafts.</p></div>
                {creatorHistory.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center text-sm text-slate-500">No content history yet.</div>
                ) : (
                  <div className="space-y-4">
                    {creatorHistory.map((item) => (
                      <div key={item.id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
                        <div className="flex items-center justify-between gap-3"><div><p className="font-semibold">{item.platform} content</p><p className="mt-1 text-xs text-slate-500">{item.createdAt}</p></div><span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">Writing history</span></div>
                        <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-400">{item.output}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* INSIGHTS */}
            {workspaceJoined && activePage === 'insights' && (
              <Insights submissions={submissions} />
            )}

            {/* SETTINGS */}
            {activePage === 'settings' && (
              <div className="max-w-4xl">
                <div className="mb-8">
                  <h1 className="text-2xl font-semibold">Settings</h1>
                  <p className="mt-1 text-sm text-slate-400">
                    Manage your profile and writing preferences.
                  </p>
                </div>

                <div className="grid gap-6 md:grid-cols-[200px_1fr]">
                  <div className="space-y-1">
                    <button
                      type="button"
                      onClick={() => setSettingsSection('profile')}
                      className={`w-full rounded-lg px-4 py-2.5 text-left text-sm ${
                        settingsSection === 'profile'
                          ? 'bg-slate-800 text-white'
                          : 'text-slate-400 hover:bg-slate-900'
                      }`}
                    >
                      Profile
                    </button>
                    <button
                      type="button"
                      onClick={() => setSettingsSection('writing')}
                      className={`w-full rounded-lg px-4 py-2.5 text-left text-sm ${
                        settingsSection === 'writing'
                          ? 'bg-slate-800 text-white'
                          : 'text-slate-400 hover:bg-slate-900'
                      }`}
                    >
                      Writing Settings
                    </button>
                  </div>

                  <div>
                    {settingsSection === 'profile' && (
                      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                        <h2 className="text-lg font-semibold">Profile</h2>
                        <div className="mt-6 space-y-5">
                          <div>
                            <p className="text-xs uppercase tracking-wider text-slate-500">User ID</p>
                            <p className="mt-2 text-sm text-slate-200">{userId}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-wider text-slate-500">Email</p>
                            <p className="mt-2 text-sm text-slate-200">{email}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-wider text-slate-500">Role</p>
                            <p className="mt-2 text-sm text-emerald-400">Creator</p>
                          </div>
                          {workspaceJoined && (
                            <div>
                              <p className="text-xs uppercase tracking-wider text-slate-500">Workspace</p>
                              <p className="mt-2 text-sm text-slate-200">{workspaceName || 'Joined workspace'}</p>
                            </div>
                          )}
                        </div>
                        {workspaceJoined && (
                          <button
                            type="button"
                            onClick={leaveWorkspace}
                            className="mt-6 rounded-lg border border-red-500/30 bg-red-500/5 px-5 py-2.5 text-sm font-semibold text-red-400 hover:bg-red-500/10"
                          >
                            Leave Workspace
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={handleLogout}
                          className="mt-8 rounded-lg border border-red-500/30 bg-red-500/5 px-5 py-2.5 text-sm font-semibold text-red-400 hover:bg-red-500/10"
                        >
                          Log out
                        </button>
                      </section>
                    )}

                    {settingsSection === 'writing' && (
                      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                        <h2 className="text-lg font-semibold">Writing Settings</h2>
                        <p className="mt-1 text-sm text-slate-400">
                          Both options are disabled by default. Turn them on when you want ENGANO to apply them to writing assistance.
                        </p>

                        <div className="mt-6 space-y-4">
                          <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-5">
                            <div>
                              <h3 className="font-medium">Auto Spelling Correction</h3>
                              <p className="mt-1 text-sm text-slate-500">
                                Automatically correct common spelling mistakes.
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => setAutoSpelling((current) => !current)}
                              className={`relative h-7 w-12 rounded-full transition ${
                                autoSpelling ? 'bg-emerald-500' : 'bg-slate-700'
                              }`}
                              aria-label="Toggle auto spelling correction"
                            >
                              <span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition ${
                                autoSpelling ? 'left-6' : 'left-1'
                              }`} />
                            </button>
                          </div>

                          <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-5">
                            <div>
                              <h3 className="font-medium">Auto Grammar Correction</h3>
                              <p className="mt-1 text-sm text-slate-500">
                                Automatically improve grammar and sentence structure.
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => setAutoGrammar((current) => !current)}
                              className={`relative h-7 w-12 rounded-full transition ${
                                autoGrammar ? 'bg-emerald-500' : 'bg-slate-700'
                              }`}
                              aria-label="Toggle auto grammar correction"
                            >
                              <span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition ${
                                autoGrammar ? 'left-6' : 'left-1'
                              }`} />
                            </button>
                          </div>
                        </div>
                      </section>
                    )}
                  </div>
                </div>
              </div>
            )}
          </main>
        </div>

        {/* JOIN WORKSPACE MODAL */}
        {showJoinWorkspaceModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
            <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-semibold">Join Workspace</h2>
                  <p className="mt-1 text-sm leading-6 text-slate-400">
                    Enter the code generated by your Brand Manager.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setShowJoinWorkspaceModal(false)
                    setWorkspaceMessage('')
                  }}
                  className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-800"
                >
                  ✕
                </button>
              </div>

              <label className="mt-6 block text-sm font-medium text-slate-300">
                Workspace Code
              </label>
              <input
                type="text"
                value={workspaceCodeInput}
                onChange={(event) => setWorkspaceCodeInput(event.target.value.toUpperCase())}
                placeholder="ENG-XXXXXX"
                className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 font-mono text-sm tracking-wider text-white outline-none placeholder:text-slate-600 focus:border-emerald-500"
              />

              {workspaceMessage && (
                <p className="mt-3 text-sm text-slate-400">{workspaceMessage}</p>
              )}

              <div className="mt-6 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowJoinWorkspaceModal(false)
                    setWorkspaceMessage('')
                  }}
                  className="rounded-lg border border-slate-700 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={joinWorkspace}
                  className="rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
                >
                  Join Workspace
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  // ==========================================
  // REVIEWER DASHBOARD
  // ==========================================

  if (
    selectedPurpose ===
      'Content Creator' &&
    currentWorkspaceRole ===
      'Reviewer'
  ) {
    return (
      <div className="min-h-screen bg-slate-950 text-white">

        <header className="flex h-16 items-center justify-between border-b border-slate-800 px-6">

          <div className="flex items-center gap-3">

            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500 font-bold text-slate-950">
              E
            </div>

            <span className="text-xl font-bold">
              ENGANO
            </span>

            <span className="rounded-full bg-yellow-500/10 px-3 py-1 text-xs font-medium text-yellow-300">
              Reviewer
            </span>

          </div>

          <div className="flex items-center gap-3">

            <button
              type="button"
              onClick={() =>
                setActivePage(
                  'settings'
                )
              }
              className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
            >
              ⚙
            </button>

            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-sm font-semibold">
              {userId
                .trim()
                .charAt(0)
                .toUpperCase() ||
                'U'}
            </div>

          </div>

        </header>

        <div className="flex min-h-[calc(100vh-4rem)]">

          <aside className="w-60 border-r border-slate-800 bg-slate-950 p-4">

            <p className="mb-4 px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Reviewer Workspace
            </p>

            <nav className="space-y-1">

              <button
                type="button"
                onClick={() =>
                  setActivePage(
                    'reviewQueue'
                  )
                }
                className={`w-full rounded-lg px-3 py-2.5 text-left text-sm ${
                  activePage ===
                  'reviewQueue'
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:bg-slate-900'
                }`}
              >
                Review Queue
              </button>

              <button
                type="button"
                onClick={() =>
                  setActivePage(
                    'history'
                  )
                }
                className={`w-full rounded-lg px-3 py-2.5 text-left text-sm ${
                  activePage ===
                  'history'
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:bg-slate-900'
                }`}
              >
                History
              </button>

              <button
                type="button"
                onClick={() =>
                  setActivePage(
                    'settings'
                  )
                }
                className={`w-full rounded-lg px-3 py-2.5 text-left text-sm ${
                  activePage ===
                  'settings'
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:bg-slate-900'
                }`}
              >
                Settings
              </button>

            </nav>

          </aside>

          <main className="flex-1 p-8">

            {activePage ===
              'reviewQueue' && (
              <ReviewQueue
                submissions={
                  submissions
                }
                onOpenSubmission={
                  openSubmission
                }
              />
            )}

            {activePage ===
              'reviewDetail' &&
              selectedSubmission && (
                <div>

                  <button
                    type="button"
                    onClick={() =>
                      setActivePage(
                        'reviewQueue'
                      )
                    }
                    className="mb-5 text-sm text-slate-400 hover:text-white"
                  >
                    ← Back to Review Queue
                  </button>

                  <div className="mb-8 flex items-center justify-between">

                    <div>
                      <h1 className="text-2xl font-semibold">
                        Review Submission
                      </h1>

                      <p className="mt-1 text-sm text-slate-400">
                        Validate AI findings and request changes when necessary.
                      </p>
                    </div>

                    <span className="rounded-full bg-yellow-400/10 px-3 py-1.5 text-sm text-yellow-300">
                      Reviewer Access
                    </span>

                  </div>

                  <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">

                    <p className="text-xs uppercase tracking-wider text-slate-500">
                      Submission
                    </p>

                    <h2 className="mt-2 text-xl font-semibold">
                      {
                        selectedSubmission.title
                      }
                    </h2>

                    <p className="mt-1 text-sm text-slate-500">
                      Submitted{' '}
                      {
                        selectedSubmission.submittedAt
                      }
                    </p>

                    <div className="mt-6 rounded-lg bg-slate-950 p-5">
                      <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">
                        {
                          selectedSubmission.content
                        }
                      </p>
                    </div>

                  </div>

                  <div className="mt-6 space-y-4">

                    {selectedSubmission.findings.map(
                      (
                        finding,
                        index
                      ) => (
                        <div
                          key={
                            index
                          }
                          className="rounded-xl border border-slate-800 bg-slate-900/60 p-5"
                        >

                          <h3 className="font-semibold">
                            {
                              finding.issue
                            }
                          </h3>

                          <p className="mt-2 text-sm leading-6 text-slate-400">
                            {
                              finding.explanation
                            }
                          </p>

                          <p className="mt-3 text-sm text-emerald-400">
                            {
                              finding.suggestion
                            }
                          </p>

                        </div>
                      )
                    )}

                  </div>

                  <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900/60 p-6">

                    <h2 className="font-semibold">
                      Reviewer Decision
                    </h2>

                    <p className="mt-1 text-sm text-slate-400">
                      Final approval belongs to the Brand Manager.
                    </p>

                    <div className="mt-5 flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={reviewerApproveSubmission}
                        className="rounded-lg bg-emerald-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
                      >
                        Approve / Send to Brand Manager
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowChangeRequestModal(true)}
                        className="rounded-lg border border-red-500/30 bg-red-500/5 px-5 py-3 text-sm font-semibold text-red-400 hover:bg-red-500/10"
                      >
                        Request Changes
                      </button>
                    </div>

                  </div>

                </div>
              )}

            {activePage === 'history' && (
              <div className="mx-auto max-w-5xl">
                <div className="mb-8">
                  <p className="text-sm font-medium text-yellow-300">Reviewer activity</p>
                  <h1 className="mt-2 text-3xl font-semibold">Review History</h1>
                  <p className="mt-2 text-sm leading-6 text-slate-400">Every review decision you made in the queue.</p>
                </div>
                {(() => {
                  const myActions = reviewerActions.filter((action) => action.workspaceId === activeWorkspaceId)
                  const directApprovals = myActions.filter((action) => action.action === 'Direct Approval').length
                  const requestedChanges = myActions.filter((action) => action.action === 'Request Changes').length
                  const aiApprovals = submissions.filter((submission) => submissionWorkspaceIds[submission.id] === activeWorkspaceId && approvalSources[submission.id] === 'AI').length
                  return (
                    <div className="space-y-6">
                      <div className="grid gap-4 md:grid-cols-3">
                        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><p className="text-sm text-slate-500">Direct AI approvals</p><p className="mt-3 text-3xl font-semibold text-emerald-400">{aiApprovals}</p></div>
                        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><p className="text-sm text-slate-500">Request Changes</p><p className="mt-3 text-3xl font-semibold text-red-400">{requestedChanges}</p></div>
                        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><p className="text-sm text-slate-500">Reviewer Approvals</p><p className="mt-3 text-3xl font-semibold text-yellow-300">{directApprovals}</p></div>
                      </div>
                      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                        <h2 className="text-lg font-semibold">Decision History</h2>
                        <div className="mt-5 space-y-3">
                          {myActions.length === 0 ? (
                            <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-500">No reviewer decisions yet.</div>
                          ) : (
                            myActions.map((action) => (
                              <div key={action.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                                <div><p className="text-sm font-medium text-slate-200">{action.title}</p><p className="mt-1 text-xs text-slate-500">{action.createdAt}</p></div>
                                <span className={`rounded-full px-3 py-1 text-xs ${action.action === 'Request Changes' ? 'bg-red-500/10 text-red-300' : 'bg-yellow-500/10 text-yellow-300'}`}>{action.action}</span>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })()}
              </div>
            )}

            {activePage ===
              'settings' && (
              <div className="max-w-3xl">

                <h1 className="text-2xl font-semibold">
                  Settings
                </h1>

                <div className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">

                  <h2 className="text-lg font-semibold">
                    Profile
                  </h2>

                  <p className="mt-4 text-sm text-slate-400">
                    User ID: {userId}
                  </p>

                  <p className="mt-2 text-sm text-slate-400">
                    Email: {email}
                  </p>

                  <button
                    type="button"
                    onClick={
                      handleLogout
                    }
                    className="mt-6 rounded-lg border border-red-500/30 px-5 py-2.5 text-sm text-red-400 hover:bg-red-500/10"
                  >
                    Log out
                  </button>

                </div>

              </div>
            )}

          </main>

        </div>

      </div>
    )
  }

  // ==========================================
  // BRAND MANAGER DASHBOARD
  // ==========================================

  return (
    <div className="min-h-screen bg-slate-950 text-white">

      {/* TOP BAR */}
      <header className="flex h-16 items-center justify-between border-b border-slate-800 px-6">

        <div className="flex items-center gap-3">

          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500 font-bold text-slate-950">
            E
          </div>

          <span className="text-xl font-bold">
            ENGANO
          </span>

          <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300">
            Brand Manager
          </span>

        </div>

        <div className="flex items-center gap-3">

          <button
            type="button"
            onClick={() =>
              setActivePage(
                'settings'
              )
            }
            className={`rounded-lg border px-3 py-2 text-sm ${
              activePage ===
              'settings'
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                : 'border-slate-700 text-slate-300 hover:bg-slate-800'
            }`}
          >
            ⚙
          </button>

          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-sm font-semibold">
            {userId
              .trim()
              .charAt(0)
              .toUpperCase() ||
              'U'}
          </div>

        </div>

      </header>

      <div className="flex min-h-[calc(100vh-4rem)]">

        {/* SIDEBAR */}
        <aside className="w-60 border-r border-slate-800 bg-slate-950 p-4">

          <p className="mb-4 px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Business Workspace
          </p>

          <nav className="space-y-1">

            <button
              type="button"
              onClick={() =>
                setActivePage(
                  'workspace'
                )
              }
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm ${
                activePage ===
                'workspace'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:bg-slate-900'
              }`}
            >
              Workspaces
            </button>

            <button
              type="button"
              onClick={() =>
                setActivePage(
                  'reviewQueue'
                )
              }
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm ${
                activePage ===
                'reviewQueue'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:bg-slate-900'
              }`}
            >
              Review Queue
            </button>

            <button
              type="button"
              onClick={() =>
                setActivePage(
                  'approvals'
                )
              }
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm ${
                activePage ===
                'approvals'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:bg-slate-900'
              }`}
            >
              Approvals
            </button>

            <button
              type="button"
              onClick={() =>
                setActivePage(
                  'guidelines'
                )
              }
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm ${
                activePage ===
                'guidelines'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:bg-slate-900'
              }`}
            >
              Brand Guidelines
            </button>

            <button
              type="button"
              onClick={() =>
                setActivePage(
                  'insights'
                )
              }
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm ${
                activePage ===
                'insights'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:bg-slate-900'
              }`}
            >
              Insights
            </button>

            <button
              type="button"
              onClick={() =>
                setActivePage(
                  'settings'
                )
              }
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm ${
                activePage ===
                'settings'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:bg-slate-900'
              }`}
            >
              Settings
            </button>

          </nav>

        </aside>

        {/* MAIN */}
        <main className="flex-1 p-8">

          {/* WORKSPACE ARCHIVE + ASSIGNMENTS */}
          {activePage === 'workspace' && (
            <div className="mx-auto max-w-6xl">
              <div className="mb-8">
                <p className="text-sm font-medium text-emerald-400">Brand Manager</p>
                <h1 className="mt-2 text-3xl font-semibold">Workspaces</h1>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                  Create and manage multiple team workspaces like Google Classroom. Each workspace has its own join code, creators, reviewers, and assignments.
                </p>
              </div>

              <div className="grid gap-6 lg:grid-cols-[1fr_1.15fr]">
                <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                  <button
                    type="button"
                    onClick={() => setArchiveExpanded((current) => !current)}
                    className="flex w-full items-center justify-between gap-3 text-left"
                  >
                    <div>
                      <h2 className="text-lg font-semibold">Workspace Archive</h2>
                      <p className="mt-1 text-sm text-slate-400">All workspaces created by you are stored here.</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-400">
                        {workspaces.length} workspace{workspaces.length === 1 ? '' : 's'}
                      </span>
                      <span className="text-slate-500">{archiveExpanded ? '▾' : '▸'}</span>
                    </div>
                  </button>

                  {archiveExpanded && (
                  <div className="mt-5 space-y-3">
                    {workspaces.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-slate-700 p-7 text-center">
                        <p className="font-medium text-slate-300">No workspaces yet</p>
                        <p className="mt-1 text-sm text-slate-500">Create your first workspace on the right.</p>
                      </div>
                    ) : (
                      workspaces.map((workspace) => (
                        <button
                          key={workspace.id}
                          type="button"
                          onClick={() => openWorkspace(workspace)}
                          className={`w-full rounded-xl border p-4 text-left transition ${
                            activeWorkspaceId === workspace.id
                              ? 'border-emerald-500/50 bg-emerald-500/5'
                              : 'border-slate-800 bg-slate-950/60 hover:border-slate-600'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div>
                              <p className="font-semibold text-white">{workspace.name}</p>
                              <p className="mt-1 font-mono text-xs text-emerald-400">{workspace.code}</p>
                            </div>
                            <span className="rounded-full bg-slate-800 px-2.5 py-1 text-xs text-slate-400">
                              {workspace.members.length} member{workspace.members.length === 1 ? '' : 's'}
                            </span>
                          </div>
                          <p className="mt-3 text-xs text-slate-500">Created {workspace.createdAt}</p>
                        </button>
                      ))
                    )}
                  </div>
                  )}

                  <div className="mt-6 border-t border-slate-800 pt-6">
                    <h3 className="font-semibold">Create another workspace</h3>
                    <input
                      type="text"
                      value={workspaceName}
                      onChange={(event) => setWorkspaceName(event.target.value)}
                      placeholder="e.g. Nimbus Marketing Team"
                      className="mt-3 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none focus:border-emerald-500"
                    />
                    <button
                      type="button"
                      onClick={createWorkspace}
                      className="mt-3 rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
                    >
                      Create Workspace
                    </button>
                  </div>
                </section>

                <section className="space-y-6">
                  {!activeWorkspace ? (
                    <div className="rounded-2xl border border-dashed border-slate-800 p-10 text-center">
                      <p className="text-lg font-medium text-slate-300">Select a workspace</p>
                      <p className="mt-2 text-sm text-slate-500">Choose a workspace from the archive to manage its team and assignments.</p>
                    </div>
                  ) : (
                    <>
                      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Active Workspace</p>
                            <h2 className="mt-2 text-2xl font-semibold">{activeWorkspace.name}</h2>
                            <p className="mt-1 font-mono text-sm text-slate-400">Join code: {activeWorkspace.code}</p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <button type="button" onClick={() => navigator.clipboard?.writeText(activeWorkspace.code)} className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800">Copy Code</button>
                            <button type="button" onClick={() => deleteWorkspace(activeWorkspace.id)} className="rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs font-semibold text-red-400 hover:bg-red-500/10">Delete Workspace</button>
                          </div>
                        </div>
                      </div>

                      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <h2 className="text-lg font-semibold">Team Members</h2>
                            <p className="mt-1 text-sm text-slate-400">Creators who joined this workspace.</p>
                          </div>
                          <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-400">
                            {activeWorkspace.members.length} member{activeWorkspace.members.length === 1 ? '' : 's'}
                          </span>
                        </div>

                        <div className="mt-5 space-y-3">
                          {activeWorkspace.members.length === 0 ? (
                            <div className="rounded-xl border border-dashed border-slate-700 p-6 text-center text-sm text-slate-500">
                              No creators have joined yet. Share {activeWorkspace.code}.
                            </div>
                          ) : (
                            activeWorkspace.members.map((member) => (
                              <div key={member.id} className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                                <div>
                                  <p className="text-sm font-medium text-slate-200">{member.userId}</p>
                                  <p className="mt-1 text-xs text-slate-500">{member.role}</p>
                                </div>
                                <span className={`rounded-full px-3 py-1 text-xs ${member.role === 'Reviewer' ? 'bg-yellow-500/10 text-yellow-300' : 'bg-purple-500/10 text-purple-300'}`}>
                                  {member.role}
                                </span>
                              </div>
                            ))
                          )}
                        </div>

                        <div className="mt-5 flex flex-col gap-3 border-t border-slate-800 pt-5 sm:flex-row">
                          <select
                            value={selectedReviewerId ?? ''}
                            onChange={(event) => setSelectedReviewerId(event.target.value ? Number(event.target.value) : null)}
                            className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-200 outline-none focus:border-emerald-500"
                          >
                            <option value="">Select creator to assign as reviewer</option>
                            {activeWorkspace.members.filter((member) => member.role === 'Creator').map((member) => (
                              <option key={member.id} value={member.id}>{member.userId}</option>
                            ))}
                          </select>
                          <button
                            type="button"
                            onClick={assignReviewer}
                            disabled={selectedReviewerId === null}
                            className="rounded-lg bg-emerald-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            Assign Reviewer
                          </button>
                        </div>
                      </div>

                      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                        <div>
                          <h2 className="text-lg font-semibold">Create Assignment</h2>
                          <p className="mt-1 text-sm text-slate-400">Give creators a topic and a deadline, just like a Google Classroom assignment.</p>
                        </div>

                        <input
                          type="text"
                          value={assignmentTitle}
                          onChange={(event) => setAssignmentTitle(event.target.value)}
                          placeholder="Assignment title — e.g. Launch announcement"
                          className="mt-5 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none focus:border-emerald-500"
                        />

                        <textarea
                          rows={4}
                          value={assignmentDescription}
                          onChange={(event) => setAssignmentDescription(event.target.value)}
                          placeholder="Tell creators what they need to write, platform requirements, tone, key points, etc."
                          className="mt-3 w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm leading-6 text-white outline-none focus:border-emerald-500"
                        />

                        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
                          <div className="flex-1">
                            <label className="block text-sm font-medium text-slate-300">Last day of submission</label>
                            <input
                              type="date"
                              value={assignmentDueDate}
                              onChange={(event) => setAssignmentDueDate(event.target.value)}
                              className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none focus:border-emerald-500"
                            />
                          </div>
                          <button
                            type="button"
                            onClick={createAssignment}
                            className="rounded-lg bg-emerald-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
                          >
                            Publish Assignment
                          </button>
                        </div>

                        {workspaceMessage && (
                          <p className="mt-4 text-sm text-emerald-300">{workspaceMessage}</p>
                        )}
                      </div>

                      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                        <h2 className="text-lg font-semibold">Assignments</h2>
                        <p className="mt-1 text-sm text-slate-400">Topics and deadlines currently assigned to creators.</p>

                        <div className="mt-5 space-y-3">
                          {workspaceAssignments.filter((assignment) => assignment.workspaceId === activeWorkspace.id).length === 0 ? (
                            <div className="rounded-xl border border-dashed border-slate-700 p-7 text-center text-sm text-slate-500">
                              No assignments published for this workspace yet.
                            </div>
                          ) : (
                            workspaceAssignments.filter((assignment) => assignment.workspaceId === activeWorkspace.id).map((assignment) => (
                              <div key={assignment.id} className="rounded-xl border border-slate-800 bg-slate-950/60 p-5">
                                <div className="flex flex-wrap items-start justify-between gap-4">
                                  <div>
                                    <h3 className="font-semibold text-white">{assignment.title}</h3>
                                    {assignment.description && <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-400">{assignment.description}</p>}
                                  </div>
                                  <span className="rounded-full bg-yellow-500/10 px-3 py-1 text-xs font-medium text-yellow-300">
                                    Due {assignment.dueDate}
                                  </span>
                                </div>
                                <p className="mt-4 text-xs text-slate-600">Published {assignment.createdAt}</p>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    </>
                  )}
                </section>
              </div>
            </div>
          )}

          {/* REVIEW QUEUE */}
          {activePage ===
            'reviewQueue' && (
            <ReviewQueue
              submissions={
                submissions
              }
              onOpenSubmission={
                openSubmission
              }
            />
          )}

          {/* REVIEW DETAIL */}
          {activePage ===
            'reviewDetail' &&
            selectedSubmission && (
              <div>

                <button
                  type="button"
                  onClick={() =>
                    setActivePage(
                      'reviewQueue'
                    )
                  }
                  className="mb-5 text-sm text-slate-400 hover:text-white"
                >
                  ← Back to Review Queue
                </button>

                <div className="mb-8 flex items-center justify-between">

                  <div>
                    <h1 className="text-2xl font-semibold">
                      Review Submission
                    </h1>

                    <p className="mt-1 text-sm text-slate-400">
                      Review the content before giving final approval.
                    </p>
                  </div>

                  <span className="rounded-full bg-yellow-400/10 px-3 py-1.5 text-sm text-yellow-300">
                    {
                      selectedSubmission.status
                    }
                  </span>

                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">

                  <p className="text-xs uppercase tracking-wider text-slate-500">
                    Submission
                  </p>

                  <h2 className="mt-2 text-xl font-semibold">
                    {
                      selectedSubmission.title
                    }
                  </h2>

                  <div className="mt-5 rounded-lg bg-slate-950 p-5">

                    <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">
                      {
                        selectedSubmission.content
                      }
                    </p>

                  </div>

                </div>

                <div className="mt-6 space-y-4">

                  {selectedSubmission.findings.map(
                    (
                      finding,
                      index
                    ) => (
                      <div
                        key={
                          index
                        }
                        className="rounded-xl border border-slate-800 bg-slate-900/60 p-5"
                      >

                        <h3 className="font-semibold">
                          {
                            finding.issue
                          }
                        </h3>

                        <p className="mt-2 text-sm leading-6 text-slate-400">
                          {
                            finding.explanation
                          }
                        </p>

                        <p className="mt-3 text-sm text-emerald-400">
                          {
                            finding.suggestion
                          }
                        </p>

                      </div>
                    )
                  )}

                </div>

                <div className="mt-8 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-6">

                  <h2 className="font-semibold">
                    Brand Manager Decision
                  </h2>

                  <p className="mt-1 text-sm text-slate-400">
                    You have final approval authority for this workspace.
                  </p>

                  <div className="mt-5 flex gap-3">

                    <button
                      type="button"
                      onClick={() =>
                        setShowChangeRequestModal(
                          true
                        )
                      }
                      className="rounded-lg border border-red-500/30 px-5 py-3 text-sm font-semibold text-red-400 hover:bg-red-500/10"
                    >
                      Request Changes
                    </button>

                    <button
                      type="button"
                      onClick={
                        approveSubmission
                      }
                      className="rounded-lg bg-emerald-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
                    >
                      Final Approve
                    </button>

                  </div>

                </div>

              </div>
            )}

          {/* BRAND MANAGER APPROVALS */}
          {activePage === 'approvals' && (
            <div className="mx-auto max-w-6xl">
              <div className="mb-8">
                <p className="text-sm font-medium text-emerald-400">Final publishing</p>
                <h1 className="mt-2 text-3xl font-semibold">Approvals</h1>
                <p className="mt-2 text-sm leading-6 text-slate-400">Review content cleared by AI or a human reviewer, then decide what is ready to publish.</p>
              </div>

              <div className="space-y-4">
                {submissions.filter((submission) => submission.status === 'Approved').length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center text-sm text-slate-500">No content is waiting for final Brand Manager approval.</div>
                ) : (
                  submissions.filter((submission) => submission.status === 'Approved').map((submission) => {
                    const source = approvalSources[submission.id] ?? 'AI'
                    const isPublished = publishedSubmissionIds.includes(submission.id)
                    return (
                      <div key={submission.id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                          <div>
                            <h2 className="text-lg font-semibold">{submission.title}</h2>
                            <p className="mt-1 text-xs text-slate-500">Submitted {submission.submittedAt}</p>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300">Cleared by {source}</span>
                            {isPublished && <span className="rounded-full bg-blue-500/10 px-3 py-1 text-xs text-blue-300">Published</span>}
                          </div>
                        </div>
                        <p className="mt-5 whitespace-pre-wrap rounded-xl bg-slate-950/70 p-5 text-sm leading-7 text-slate-300">{submission.content}</p>
                        {!isPublished && (
                          <div className="mt-5 flex justify-end">
                            <button type="button" onClick={() => publishSubmission(submission)} className="rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400">Publish Content</button>
                          </div>
                        )}
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}

          {/* GUIDELINES */}
          {activePage ===
            'guidelines' && (
            <BrandGuidelines
              guidelines={
                guidelines
              }
              setGuidelines={
                updateGuidelinesForWorkspace
              }
            />
          )}

          {/* BRAND MANAGER INSIGHTS */}
          {activePage === 'insights' && (
            <div className="mx-auto max-w-6xl">
              <div className="mb-8">
                <p className="text-sm font-medium text-emerald-400">Workspace Report Card</p>
                <h1 className="mt-2 text-3xl font-semibold">Insights</h1>
                <p className="mt-2 text-sm leading-6 text-slate-400">Select a workspace to view its content governance analytics.</p>
              </div>

              <select
                value={selectedInsightWorkspaceId ?? ''}
                onChange={(event) => setSelectedInsightWorkspaceId(event.target.value ? Number(event.target.value) : null)}
                className="mb-6 w-full max-w-md rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-200 outline-none focus:border-emerald-500"
              >
                <option value="">Select a workspace</option>
                {workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
                ))}
              </select>

              {(() => {
                const workspaceId = selectedInsightWorkspaceId
                const workspaceSubmissions = submissions.filter((submission) => submissionWorkspaceIds[submission.id] === workspaceId)
                const workspaceActions = reviewerActions.filter((action) => action.workspaceId === workspaceId)
                const approved = workspaceSubmissions.filter((submission) => submission.status === 'Approved').length
                const changes = workspaceActions.filter((action) => action.action === 'Request Changes').length
                const reviewerApprovals = workspaceActions.filter((action) => action.action === 'Direct Approval').length
                const aiApprovals = workspaceSubmissions.filter((submission) => approvalSources[submission.id] === 'AI').length
                const published = workspaceSubmissions.filter((submission) => publishedSubmissionIds.includes(submission.id)).length

                if (!workspaceId) {
                  return <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center text-sm text-slate-500">Choose a workspace to see its report card.</div>
                }

                return (
                  <div className="space-y-6">
                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                      <h2 className="text-xl font-semibold">{workspaces.find((workspace) => workspace.id === workspaceId)?.name}</h2>
                      <p className="mt-1 text-sm text-slate-400">Workspace governance report</p>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                      {[
                        ['Submissions', workspaceSubmissions.length, 'text-white'],
                        ['AI Approvals', aiApprovals, 'text-emerald-400'],
                        ['Reviewer Approvals', reviewerApprovals, 'text-yellow-300'],
                        ['Changes Requested', changes, 'text-red-400'],
                        ['Published', published, 'text-blue-400'],
                      ].map(([label, value, color]) => (
                        <div key={String(label)} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
                          <p className="text-sm text-slate-500">{label}</p>
                          <p className={`mt-3 text-3xl font-semibold ${color}`}>{value}</p>
                        </div>
                      ))}
                    </div>

                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                      <h2 className="text-lg font-semibold">Governance Summary</h2>
                      <div className="mt-5 grid gap-4 md:grid-cols-3">
                        <div className="rounded-xl bg-slate-950/70 p-5"><p className="text-xs uppercase tracking-wider text-slate-500">Approval rate</p><p className="mt-2 text-2xl font-semibold text-emerald-400">{workspaceSubmissions.length ? Math.round((approved / workspaceSubmissions.length) * 100) : 0}%</p></div>
                        <div className="rounded-xl bg-slate-950/70 p-5"><p className="text-xs uppercase tracking-wider text-slate-500">Review intervention</p><p className="mt-2 text-2xl font-semibold text-yellow-300">{changes + reviewerApprovals}</p></div>
                        <div className="rounded-xl bg-slate-950/70 p-5"><p className="text-xs uppercase tracking-wider text-slate-500">Workspace members</p><p className="mt-2 text-2xl font-semibold text-white">{workspaces.find((workspace) => workspace.id === workspaceId)?.members.length ?? 0}</p></div>
                      </div>
                    </div>
                  </div>
                )
              })()}
            </div>
          )}

          {/* SETTINGS */}
          {activePage ===
            'settings' && (
            <div className="max-w-3xl">

              <h1 className="text-2xl font-semibold">
                Settings
              </h1>

              <div className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">

                <h2 className="text-lg font-semibold">
                  Profile
                </h2>

                <div className="mt-5 space-y-4">

                  <div>
                    <p className="text-xs uppercase tracking-wider text-slate-500">
                      User ID
                    </p>

                    <p className="mt-1 text-sm text-slate-200">
                      {
                        userId
                      }
                    </p>
                  </div>

                  <div>
                    <p className="text-xs uppercase tracking-wider text-slate-500">
                      Email
                    </p>

                    <p className="mt-1 text-sm text-slate-200">
                      {
                        email
                      }
                    </p>
                  </div>

                  <div>
                    <p className="text-xs uppercase tracking-wider text-slate-500">
                      Role
                    </p>

                    <p className="mt-1 text-sm text-emerald-400">
                      Brand Manager
                    </p>
                  </div>

                </div>

                <button
                  type="button"
                  onClick={
                    handleLogout
                  }
                  className="mt-7 rounded-lg border border-red-500/30 px-5 py-2.5 text-sm font-semibold text-red-400 hover:bg-red-500/10"
                >
                  Log out
                </button>

              </div>

            </div>
          )}

        </main>

      </div>

      {/* CHANGE REQUEST MODAL */}
      {showChangeRequestModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">

          <div className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">

            <div className="flex items-start justify-between">

              <div>
                <h2 className="text-lg font-semibold">
                  Request Changes
                </h2>

                <p className="mt-1 text-sm text-slate-400">
                  Tell the creator what needs to be changed.
                </p>
              </div>

              <button
                type="button"
                onClick={() => {
                  setShowChangeRequestModal(
                    false
                  )
                  setChangeRequestComment(
                    ''
                  )
                }}
                className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-800"
              >
                ✕
              </button>

            </div>

            <textarea
              rows={5}
              value={
                changeRequestComment
              }
              onChange={(
                event
              ) =>
                setChangeRequestComment(
                  event.target.value
                )
              }
              placeholder="Explain what the creator should change..."
              className="mt-6 w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm leading-6 text-white outline-none focus:border-red-500"
            />

            <div className="mt-5 flex justify-end gap-3">

              <button
                type="button"
                onClick={() => {
                  setShowChangeRequestModal(
                    false
                  )
                  setChangeRequestComment(
                    ''
                  )
                }}
                className="rounded-lg border border-slate-700 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={
                  requestChanges
                }
                disabled={
                  !changeRequestComment.trim()
                }
                className="rounded-lg bg-red-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-400 disabled:opacity-40"
              >
                Request Changes
              </button>

            </div>

          </div>

        </div>
      )}

    </div>
  )
}

export default App