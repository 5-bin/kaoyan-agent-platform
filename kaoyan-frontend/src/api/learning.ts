import request from './request'
export interface LearningGroup {
  knowledgePointId: string; subject: string; knowledgePoint: string; difficulty: string
  samples: number; correct: number; assisted: number; unknown: number; masteryIndex: number | null
  sampleStatus: string; weight: number; priority: number | null; anomaly: boolean
}
export interface LearningProfile {
  revision: number; algorithmVersion: string; blueprintVersion: string; referenceScore: number | null
  coverage: number; independentSamples: number; assistedSamples: number; unknownSamples: number
  sufficient: boolean; status: string; updatedAt: string; groups: LearningGroup[]; notices: string[]
}
export interface ManagedItem {
  itemId: number; questionId: number; orderIndex: number; subject: string; knowledgePoint: string; difficulty: string
  content: string; optionA: string; optionB: string; optionC: string; optionD: string
  userAnswer: string | null; draftAnswer: string | null; submitted: boolean; hintLevelUsed: number
  withdrawn: boolean; isCorrect: number | null; answer: string | null; analysis: string | null
}
export interface ManagedState {
  sessionId: string; kind: string; state: string; revision: number; currentIndex: number
  blueprint: { id: string; missing?: { subject: string; difficulty: string; missing: number }[] }; items: ManagedItem[]
}
export interface ManagedResult {
  session: ManagedState; total: number; answered: number; withdrawn: number; unanswered: number
  correct: number | null; accuracy: number | null; assisted: number; independentAccuracy: number | null
  diagnosticReferenceScore: number | null; notice: string; profilePending: boolean; profileUpdateFailed?: boolean
}
export interface RecommendationSettings {
  revision: number; enabled: boolean; preferences: Record<string, unknown>; status: string
  pendingReason?: string; lastTaskId?: string; profileRevision?: number; updatedAt?: string
}
export const learningStatus = () => request.get<unknown, { enabled: boolean }>('/learning/status')
export const startDiagnostic = () => request.post<unknown, { sessionId: string; actualCount: number; missing: unknown[] }>('/diagnostics/sessions')
export const learningProfile = () => request.get<unknown, LearningProfile>('/learning/profile')
export const learningHistory = (pageNum = 1) => request.get<unknown, { list: LearningProfile[]; total: number }>('/learning/profile/history', { params: { pageNum, pageSize: 10 } })
export const recommendationSettings = () => request.get<unknown, RecommendationSettings>('/learning/recommendation-settings')
export const saveRecommendationSettings = (value: Pick<RecommendationSettings, 'revision' | 'enabled' | 'preferences'>) => request.put<unknown, RecommendationSettings>('/learning/recommendation-settings', value)
export const managedState = (id: string) => request.get<unknown, ManagedState>(`/practice/sessions/${id}/state`)
export const saveProgress = (id: string, revision: number, currentIndex: number, answers: Record<number, string>) => request.put<unknown, ManagedState>(`/practice/sessions/${id}/progress`, { revision, currentIndex, answers })
export const finishManaged = (id: string) => request.post<unknown, ManagedResult>(`/practice/sessions/${id}/finish`)
export const managedResult = (id: string) => request.get<unknown, ManagedResult>(`/practice/sessions/${id}/result`)
export const managedHint = (id: string, item: number, level: number) => request.post<unknown, { available: boolean; text?: string; hintLevelUsed: number }>(`/practice/sessions/${id}/items/${item}/hints`, { level })
export const submitManaged = (id: string, item: ManagedItem, answer: string, clientRequestId: string) => request.post(`/practice/sessions/${id}/answer`, { questionId: item.questionId, itemId: item.itemId, answer, clientRequestId })
