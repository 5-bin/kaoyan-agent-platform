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
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED'
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
export interface TaskResult {
  outcome: 'COMPLETED' | 'NEEDS_INPUT' | 'UNSUPPORTED'; answer: string
  resolvedTaskType: Task['taskType']; explanationMode: 'rules' | 'ai' | 'fallback'
  releaseId: string; references: SourceReference[]; followUp?: string[]; notice?: string
  candidates?: SchoolCandidate[]; coverage?: string; weakPoints?: string[]; accuracy?: number
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

export interface PracticeRecord {
  id: number
  userId: number
  sessionId: string
  questionId: number
  orderIndex: number
  userAnswer?: string
  isCorrect?: number
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
