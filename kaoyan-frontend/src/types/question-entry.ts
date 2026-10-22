import type { Question } from './api'

export type SourceType = 'REAL_EXAM' | 'MOCK' | 'ORIGINAL'
export interface QuestionEntry {
  subject: string; knowledgePoint: string; difficulty: 'EASY' | 'MEDIUM' | 'HARD'
  content: string; optionA: string; optionB: string; optionC: string; optionD: string
  answer: string; analysis: string; sourceType: SourceType; sourceName: string
  sourceLocator: string; sourceYear?: number; sourceQuestionNo: string; permissionNote: string
}
export interface QuestionUpdate extends QuestionEntry { version: number }

export interface AdminQuestion extends Question {
  version: number
  sourceType?: SourceType | null
  sourceName?: string | null
  sourceLocator?: string | null
  sourceYear?: number | null
  sourceQuestionNo?: string | null
  permissionNote?: string | null
  reviewerUserId?: number | null
  reviewedAt?: string | null
  reviewComment?: string | null
}
