import request from './request'
import type { Question, StudentQuestion } from '@/types/api'

export const getPracticeQuestions = (params: {
  subject?: string
  difficulty?: string
  limit?: number
}) => request.get<unknown, StudentQuestion[]>('/questions/practice', { params })

export const getQuestionDetail = (id: number) =>
  request.get<unknown, StudentQuestion>(`/questions/${id}`)

export const getAdminPending = (params: { pageNum: number; pageSize: number }) =>
  request.get<unknown, { list: Question[] }>('/questions/admin/pending', { params })

export const reviewQuestion = (id: number, data: { status: string; comment?: string }) =>
  request.post(`/questions/admin/${id}/review`, data)
