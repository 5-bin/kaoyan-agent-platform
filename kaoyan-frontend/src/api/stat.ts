import request from './request'
import type { StudyStat } from '@/types/api'

export const getTodayStat = () => request.get<unknown, StudyStat>('/stats/today')

export const getRangeStat = (params: { from: string; to: string }) =>
  request.get<unknown, StudyStat[]>('/stats/range', { params })

export const getOverview = () => request.get('/stats/overview')
