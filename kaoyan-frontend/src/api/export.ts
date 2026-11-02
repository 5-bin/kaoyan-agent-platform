import request from './request'

export type ExportSource =
  | { source: 'NOTE'; documentId: string; version: number }
  | { source: 'LEARNING_REPORT' }
  | { source: 'TASK_RESULT'; taskId: string; part: 'ANSWER' | 'STUDY_PLAN' | 'NOTE_PROPOSAL' }
export type ExportFormat = 'docx' | 'pdf' | 'md'
export interface ExportPreview {
  id: string; title: string; sourceVersion: string; generatedAt: string; expiresAt: string; markdown: string
  charts: { title: string; png: string }[]
}
export const previewExport = (source: ExportSource, signal: AbortSignal) =>
  request.post<unknown, ExportPreview>('/exports/preview', source, { signal })
export const downloadExport = (id: string, format: ExportFormat, signal: AbortSignal) =>
  request.get<unknown, Blob>(`/exports/${id}/file`, { params: { format }, responseType: 'blob', signal })
