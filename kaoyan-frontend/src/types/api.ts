export interface Result<T = unknown> {
  code: number
  message: string
  data: T
}

export interface PageResult<T = unknown> {
  total: number
  page: number
  size: number
  list: T[]
}

export interface User {
  id: number
  username: string
  role: 'ADMIN' | 'STUDENT'
  status: number
  avatarUrl?: string
  targetSchool?: string
  targetMajor?: string
  examYear?: number
  background?: string
}

export interface Task {
  id: string
  userId: number
  taskType: 'KNOWLEDGE_QA' | 'SCHOOL_RECOMMEND' | 'PRACTICE_SUMMARY' | 'CHAT'
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'CANCELLED'
  inputPayload?: Record<string, unknown>
  resultPayload?: TaskResult
  releaseId?: string
  errorMessage?: string
  createdAt: string
}

export interface SourceReference {
  id: string; title: string; url: string; locator: string; version: string; retrievedAt: string; excerpt: string
}
export interface SchoolCandidate {
  programId: string; school: string; college: string; major: string; majorCode: string; year: number
  degreeType: 'academic' | 'professional'; region: string; studyMode: string; examSubjects: string[]
  matchedConditions: string[]; pendingChecks: string[]; sourceIds: string[]; explanation: string
}
export interface AssistantAction {
  id: string; type: string; status: 'PENDING' | 'SUCCESS' | 'DISMISSED' | 'FAILED'; title: string
  count: number; requiresConfirmation: boolean; result?: { sessionId?: string; actualCount?: number }
  requestedCount?: number; targets?: { title: string; resource: AssistantEvidence['resource'] }[]
}
export interface AssistantEvidence {
  ref: string; kind: string; title: string; locator?: string; version?: string
  resource?: { type: 'question' | 'document' | 'practice' | 'stats'; id?: string | number }
}
export interface TaskResult {
  outcome: 'COMPLETED' | 'NEEDS_INPUT' | 'UNSUPPORTED'; answer: string
  resolvedTaskType: Task['taskType']; explanationMode: 'rules' | 'ai' | 'fallback'
  releaseId: string; references: SourceReference[]; followUp?: string[]; notice?: string
  candidates?: SchoolCandidate[]; coverage?: string; weakPoints?: string[]; accuracy?: number
  evidence?: AssistantEvidence[]; actions?: AssistantAction[]
  conditions?: Record<string, unknown>
  documentProposal?: { operation: 'create' | 'update'; documentId?: string; baseVersion?: number; title: string; content: string }
}

export interface Document {
  id: number
  title: string
  subject: string
  content: string
  sourceUrl?: string
  status: 'DRAFT' | 'PENDING_REVIEW' | 'PUBLISHED' | 'REJECTED'
  createdAt: string
}

export interface School {
  id: number
  name: string
  province?: string
  level?: string
}

export interface SchoolDetail {
  id: number
  schoolId: number
  majorName: string
  majorCode?: string
  year: number
  enrollmentCount?: number
  scoreLine?: number
  remark?: string
}

export interface RecommendRecord {
  id: number
  userId: number
  schoolId: number
  reason?: string
  score?: number
  createdAt: string
}

export interface Question {
  id: number
  subject: string
  knowledgePoint?: string
  content: string
  optionA?: string
  optionB?: string
  optionC?: string
  optionD?: string
  answer: string
  analysis?: string
  difficulty: 'EASY' | 'MEDIUM' | 'HARD'
  questionType: string
  active: number
  reviewStatus: string
}

export type StudentQuestion = Pick<Question, 'id' | 'subject' | 'knowledgePoint' | 'content' |
  'optionA' | 'optionB' | 'optionC' | 'optionD' | 'difficulty' | 'questionType'> & { version?: number }

export interface PracticeRecord {
  id: number
  sessionId: string
  questionId: number
  orderIndex: number
  userAnswer?: string
  isCorrect?: number | null
  gradingStatus?: string
  answeredAt?: string
}

export interface UserQuestionMark {
  id: number
  userId: number
  questionId: number
  isFavorite: number
  isWrong: number
  wrongCount: number
  lastWrongAt?: string
}

export interface StudyStat {
  id: number
  userId: number
  statDate: string
  questionCount: number
  correctCount: number
  studyMinutes: number
}
