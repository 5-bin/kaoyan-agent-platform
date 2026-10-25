import request, { handleAuthFailure } from './request'
import { useUserStore } from '@/stores/user'
import type { PageResult, Task, TaskResult } from '@/types/api'

export interface AssistantPageContext {
  page: 'wrong' | 'favorite' | 'stat' | 'documents' | 'practice' | 'notes'
  subject?: string; from?: string; to?: string; sessionId?: string; documentId?: number
  selectedQuestionIds?: number[]; visibleQuestionIds?: number[]
}
export const deleteConversation = (id: string) => request.delete(`/conversations/${id}`)
export const clearConversations = () => request.delete('/conversations')
export const confirmAction = (id: string, actionId: string) => request.post<unknown, import('@/types/api').AssistantAction>(`/conversations/${id}/actions/${actionId}/confirm`)
export const dismissAction = (id: string, actionId: string) => request.post<unknown, import('@/types/api').AssistantAction>(`/conversations/${id}/actions/${actionId}/dismiss`)
export interface Conversation { id: string; title: string; conditions: Record<string, unknown> }
export interface Generation {
  taskId: string; attemptNo: number; status: Task['status']; version: number; stage?: string
  errorMessage?: string; draft?: Record<string, string>; result?: TaskResult
}
export interface ChatMessage { id: string; sequenceNo: number; content: string; attempts: Generation[]; createdAt: string }
export interface PersonalDocument { id: string; title: string; content: string; version: number }
export interface DocumentVersion extends PersonalDocument { documentId: string; sourceTaskId?: string; createdAt: string }
export const createConversation = () => request.post<unknown, Conversation>('/conversations')
export const listConversations = (pageNum = 1) => request.get<unknown, PageResult<Conversation>>('/conversations', { params: { pageNum, pageSize: 5 } })
export const listMessages = (id: string, pageNum = 1) => request.get<unknown, PageResult<ChatMessage> & { conversation: Conversation }>(`/conversations/${id}/messages`, { params: { pageNum, pageSize: 20 } })
export const sendMessage = (id: string, data: { query: string; clientRequestId: string; documentId?: string; documentVersion?: number; pageContext?: AssistantPageContext; referenceTaskId?: string }) =>
  request.post<unknown, { taskId: string; messageId: string }>(`/conversations/${id}/messages`, data)
export const retryMessage = (id: string, messageId: string, clientRequestId: string) =>
  request.post<unknown, { taskId: string; messageId: string }>(`/conversations/${id}/messages/${messageId}/retry`, { clientRequestId })
export const cancelGeneration = (id: string, taskId: string) => request.post(`/conversations/${id}/generations/${taskId}/cancel`)
export const listPersonalDocuments = (pageNum = 1, pageSize = 20) => request.get<unknown, PageResult<PersonalDocument>>('/personal-documents', { params: { pageNum, pageSize } })
export const getPersonalDocument = (id: string) => request.get<unknown, PersonalDocument>(`/personal-documents/${id}`)
export const getDocumentVersion = (id: string, version: number) => request.get<unknown, PersonalDocument>(`/personal-documents/${id}/versions/${version}`)
export const documentVersions = (id: string, pageNum = 1) => request.get<unknown, PageResult<DocumentVersion>>(`/personal-documents/${id}/versions`, { params: { pageNum, pageSize: 20 } })
export const savePersonalDocument = (data: { title: string; content: string; baseVersion?: number }, id?: string) =>
  id ? request.put<unknown, PersonalDocument>(`/personal-documents/${id}`, data) : request.post<unknown, PersonalDocument>('/personal-documents', data)
export const applyDocument = (id: string, taskId: string, data: { title: string; content: string }) =>
  request.post<unknown, PersonalDocument>(`/conversations/${id}/generations/${taskId}/apply-document`, data)

export async function subscribeGeneration(id: string, taskId: string, signal: AbortSignal, receive: (event: string, value: Record<string, unknown>) => void) {
  const token = useUserStore().token
  const controller = new AbortController()
  const cancel = () => controller.abort()
  signal.addEventListener('abort', cancel, { once: true })
  if (signal.aborted) controller.abort()
  let idle: ReturnType<typeof setTimeout>
  const resetIdle = () => { clearTimeout(idle); idle = setTimeout(cancel, 25000) }
  resetIdle()
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
  try {
    const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
    const response = await fetch(`${base}/conversations/${id}/generations/${taskId}/stream`, {
      headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' }, cache: 'no-store', signal: controller.signal
    })
    if (token !== useUserStore().token) throw new Error('账号已切换')
    if (!response.ok) {
      handleAuthFailure(response.status, token)
      throw new Error(response.status === 404 ? '会话不存在或无权访问' : '连接暂时不可用')
    }
    if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) throw new Error('响应不是消息流')
    reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (!signal.aborted) {
      const chunk = await reader.read()
      if (chunk.done) break
      resetIdle()
      if (token !== useUserStore().token) throw new Error('账号已切换')
      buffer = (buffer + decoder.decode(chunk.value, { stream: true })).replace(/\r\n/g, '\n')
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2)
        const lines = frame.split('\n')
        const event = lines.find(line => line.startsWith('event:'))?.slice(6).trim() || 'message'
        const data = lines.filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n')
        if (data) receive(event, JSON.parse(data))
      }
      if (buffer.length > 250000) throw new Error('消息流过长')
    }
  } finally {
    clearTimeout(idle!)
    signal.removeEventListener('abort', cancel)
    await reader?.cancel().catch(() => {})
  }
}
