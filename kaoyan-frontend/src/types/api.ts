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
  taskType: 'KNOWLEDGE_QA' | 'SCHOOL_RECOMMEND'
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED'
  inputPayload?: Record<string, unknown>
  resultPayload?: Record<string, unknown>
  errorMessage?: string
  createdAt: string
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
