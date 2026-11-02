import request from './request'
import type { Document, PageResult } from '@/types/api'

export const getPublishedDocuments = (params: { subject?: string }) =>
  request.get<unknown, Document[]>('/documents', { params })

export const getAdminDocumentList = (params: {
  status?: string
  pageNum: number
  pageSize: number
}) => request.get<unknown, PageResult<Document>>('/documents/admin/list', { params })

export const reviewDocument = (id: number, data: { status: string; comment?: string }) =>
  request.post(`/documents/admin/${id}/review`, data)
