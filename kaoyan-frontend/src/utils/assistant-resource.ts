import type { AssistantEvidence } from '@/types/api'
export function resourceRoute(resource?: AssistantEvidence['resource']) {
  if (!resource) return undefined
  const id = String(resource.id ?? '')
  if (resource.type === 'stats') return '/stat'
  if (resource.type === 'document' && /^\d+$/.test(id)) return { path: '/documents', query: { documentId: id } }
  if (resource.type === 'question' && /^\d+$/.test(id)) return { path: '/practice', query: { questionId: id } }
  if (resource.type === 'practice' && /^[a-zA-Z0-9-]{1,64}$/.test(id)) return `/practice/session/${encodeURIComponent(id)}`
  return undefined
}
export function safeSourceUrl(value?: string) {
  if (!value) return undefined
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password ? value : undefined } catch { return undefined }
}
