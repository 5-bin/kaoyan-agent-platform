import request from './request'

import type { PracticeRecord } from '@/types/api'

export interface AnswerResult {
  recordId?: number
  questionId: number
  userAnswer: string
  isCorrect: 0 | 1
  answer: string
  analysis?: string
}

export const startSession = (data: { subject: string; difficulty?: string; count: number }) =>
  request.post<unknown, { sessionId: string }>('/practice/sessions', data)

export const answerQuestion = (
  sessionId: string,
  data: { questionId: number; answer: string }
) => request.post<unknown, AnswerResult>(`/practice/sessions/${sessionId}/answer`, data)

export const getSessionDetail = (sessionId: string) =>
  request.get<unknown, PracticeRecord[]>(`/practice/sessions/${sessionId}`)

export const getSessionSummary = (sessionId: string) =>
  request.get(`/practice/sessions/${sessionId}/summary`)

export interface SessionSummary {
  sessionId: string
  total: number
  answered: number
  correct: number
  accuracy: number
  finishedAt: string
}

export const getSessionPage = (params: { pageNum: number; pageSize: number }) =>
  request.get<unknown, { total: number; list: SessionSummary[] }>('/practice/sessions/page', { params })

export interface ReviewRecord {
  recordId?: number
  questionId: number
  orderIndex: number
  userAnswer?: string
  isCorrect?: number | null
  snapshotStatus?: string
  version?: number
  subject?: string
  knowledgePoint?: string
  content?: string
  optionA?: string
  optionB?: string
  optionC?: string
  optionD?: string
  answer?: string
  analysis?: string
  difficulty?: string
}

export const getReviewPage = (sessionId: string, params: { pageNum: number; pageSize: number }) =>
  request.get<unknown, { total: number; list: ReviewRecord[] }>(`/practice/sessions/${sessionId}/review`, { params })

export const triggerAiSummary = (sessionId: string) =>
  request.post<unknown, any>(`/practice/sessions/${sessionId}/ai-summary`)

export const abandonSession = (sessionId: string) =>
  request.delete(`/practice/sessions/${sessionId}`)
