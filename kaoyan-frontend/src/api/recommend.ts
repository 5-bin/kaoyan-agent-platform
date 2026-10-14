import request from './request'
import type { RecommendRecord } from '@/types/api'

export const generateRecommend = () =>
  request.post<unknown, RecommendRecord[]>('/recommends/generate')

export const getRecommendList = () =>
  request.get<unknown, RecommendRecord[]>('/recommends')

export const deleteRecommend = (id: number) =>
  request.delete(`/recommends/${id}`)
