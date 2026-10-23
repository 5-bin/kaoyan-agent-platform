import request from './request'
import type { StudyStat } from '@/types/api'

export const getTodayStat = () => request.get<unknown, StudyStat>('/stats/today')

export const getRangeStat = (params: { from: string; to: string }) =>
  request.get<unknown, StudyStat[]>('/stats/range', { params })

export interface LearningStat {
  questionCount: number; correctCount: number; uniqueQuestions: number; wrongCount: number; accuracy: number | null
  from: string; to: string; daily: { statDate: string; questionCount: number; correctCount: number }[]
  knowledgePoints: { knowledgePoint: string; questionCount: number; correctCount: number }[]
}
export const getLearningStat = (params?: { from?: string; to?: string; subject?: string }) => request.get<unknown, LearningStat>('/stats/learning', { params })
export const getOverview = () => request.get('/stats/overview')
