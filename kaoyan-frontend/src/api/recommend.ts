import request from './request'
import type { Task } from '@/types/api'
export const generateRecommend = (input: Record<string, unknown>) =>
  request.post<unknown, Task>('/recommends/generate', input)
export const getRecommendList = () => request.get<unknown, Task[]>('/recommends')
export const deleteRecommend = (id: string) => request.delete(`/recommends/${encodeURIComponent(id)}`)
