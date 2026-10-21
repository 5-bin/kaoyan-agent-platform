import request from './request'

export interface MarkItem {
  questionId: number
  wrongCount?: number
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
  isFavorite?: number
  snapshotStatus?: string
  version?: number
}

export const addWrong = (questionId: number) =>
  request.post(`/marks/wrong/${questionId}`)

export const removeWrong = (questionId: number) =>
  request.delete(`/marks/wrong/${questionId}`)

export const addFavorite = (questionId: number) =>
  request.post(`/marks/favorite/${questionId}`)

export const removeFavorite = (questionId: number) =>
  request.delete(`/marks/favorite/${questionId}`)

export const getWrongPage = (params: { pageNum: number; pageSize: number }) =>
  request.get<unknown, { total: number; list: MarkItem[] }>('/marks/wrong', { params })

export const getFavoritePage = (params: { pageNum: number; pageSize: number }) =>
  request.get<unknown, { total: number; list: MarkItem[] }>('/marks/favorite', { params })
