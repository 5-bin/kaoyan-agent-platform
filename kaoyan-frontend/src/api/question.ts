import request from './request'
import type { StudentQuestion, PageResult } from '@/types/api'
import type { QuestionEntry, QuestionUpdate, AdminQuestion } from '@/types/question-entry'

export const getPracticeQuestions = (params: {
  subject?: string
  difficulty?: string
  limit?: number
}) => request.get<unknown, StudentQuestion[]>('/questions/practice', { params })

export const getQuestionDetail = (id: number) =>
  request.get<unknown, StudentQuestion>(`/questions/${id}`)

export const getAdminPending = (params: { pageNum: number; pageSize: number }) =>
  request.get<unknown, PageResult<AdminQuestion>>('/questions/admin/pending', { params })

export const getAdminQuestion = (id: number) =>
  request.get<unknown, AdminQuestion>(`/questions/admin/${id}`)

export const createQuestion = (data: QuestionEntry) =>
  request.post<unknown, AdminQuestion>('/questions/admin', data)

export const updateQuestion = (id: number, data: QuestionUpdate) =>
  request.put<unknown, AdminQuestion>(`/questions/admin/${id}`, data)

export const reviewQuestion = (id: number, data: { status: 'APPROVED' | 'REJECTED'; comment?: string; version: number }) =>
  request.post(`/questions/admin/${id}/review`, data)

export const changeQuestionActive = (id: number, data: { active: 0 | 1; version: number }) =>
  request.put<unknown, AdminQuestion>(`/questions/admin/${id}/active`, data)
