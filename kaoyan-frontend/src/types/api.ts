export interface PageResult<T = unknown> {
  total: number
  page: number
  size: number
  list: T[]
}

export interface User {
  id: number
  username: string
  role: 'ADMIN' | 'STUDENT'
  status: number
  avatarUrl?: string
  targetSchool?: string
  targetMajor?: string
  examYear?: number
  background?: string
}

export interface Task {
  id: string
  userId: number
  taskType: 'KNOWLEDGE_QA' | 'SCHOOL_RECOMMEND' | 'PRACTICE_SUMMARY' | 'CHAT' | 'WRONG_QUESTION_TUTOR'
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'CANCELLED'
  inputPayload?: Record<string, unknown>
  tutoring?: { recordId: number; query: string; parentTaskId?: string | null; messages: { role: 'user' | 'assistant'; content: string }[] } | null
  resultPayload?: TaskResult
  releaseId?: string
  errorMessage?: string
  createdAt: string
}

export interface SourceReference {
  id: string; title: string; url: string; locator: string; version: string; retrievedAt: string; excerpt: string
}
export interface CitationSupport {
  status: 'SUPPORTED' | 'PARTIAL' | 'UNSUPPORTED' | 'NOT_CHECKED'
  checked: number; supported: number; ratio: number
  unsupported: { text: string; reason: string; sourceIds?: string[] }[]
  items?: { text: string; sourceIds: string[]; supported: boolean; reason?: string; ratio?: number }[]
}
export interface SchoolCandidate {
  programId: string; school: string; college: string; major: string; majorCode: string; year: number
  degreeType: 'academic' | 'professional'; region: string; studyMode: string; examSubjects: string[]
  matchedConditions: string[]; pendingChecks: string[]; sourceIds: string[]; explanation: string
  citationSupport?: CitationSupport
}
export interface AssistantAction {
  id: string; type: string; status: 'PENDING' | 'SUCCESS' | 'DISMISSED' | 'FAILED'; title: string
  count: number; requiresConfirmation: boolean; result?: { sessionId?: string; actualCount?: number }
  requestedCount?: number; targets?: { title: string; resource: AssistantEvidence['resource']; matchMethod?: 'LABEL' | 'SEMANTIC'; matchTopic?: string }[]
}
export interface AssistantEvidence {
  ref: string; kind: string; title: string; locator?: string; version?: string
  matchMethod?: 'LABEL' | 'SEMANTIC'; matchTopic?: string; summary?: string
  resource?: { type: 'question' | 'document' | 'practice' | 'stats'; id?: string | number }
}
export interface HistoricalComparison {
  programId: string; status: string; year?: number; score?: number; gap?: number; notice: string
  source?: { title: string; url: string; locator: string; version: string; retrievedAt: string }
}
export interface AdmissionLinks {
  schoolCode: string; schoolName: string; registeredYear: number; entryUrls: string[]
}
/** Legacy records are read only for their registered school code. */
export interface LegacyAdmissionCheck {
  query?: { schoolCode?: string }
}

/** Present only when the same layer's explanationMode is fallback. */
export type FallbackReason = 'TIMEOUT' | 'UNAVAILABLE' | 'BUDGET_EXHAUSTED' | 'INPUT_TOO_LONG' | 'INVALID_OUTPUT' | 'EVIDENCE_MISMATCH' | 'NUMBER_MISMATCH'

export interface TaskResult {
  clarificationOptions?: { label: string; reply: string }[]
  sections?: { agent: 'LEARNING' | 'SCHOOL' | 'KNOWLEDGE' | 'PRACTICE' | 'NOTE' | 'STUDY_PLAN'; outcome: 'COMPLETED' | 'NEEDS_INPUT' | 'UNSUPPORTED'; explanationMode: 'rules' | 'ai' | 'fallback'; fallbackReason?: FallbackReason; notice?: string }[]
  partial?: boolean
  operation?: string
  questionRefs?: string[]
  count?: number
  target?: 'selected' | 'visible' | 'wrong' | 'favorite' | 'normal'
  total?: number
  readCount?: number
  admissionLinks?: AdmissionLinks
  schoolCatalog?: SchoolCatalog
  admissionCheck?: LegacyAdmissionCheck
  studyPlan?: { days: { day: number; topic: string; tasks: string[] }[]; basis: string[] }
  resultSchemaVersion?: number
  learningSnapshot?: { profileRevision: number; referenceScore: number | null; coverage: number; blueprintVersion: string; calibrated: false }
  triggerReason?: string
  historicalComparisons?: HistoricalComparison[]
  outcome: 'COMPLETED' | 'NEEDS_INPUT' | 'UNSUPPORTED'; answer: string
  resolvedTaskType: Task['taskType']; explanationMode: 'rules' | 'ai' | 'fallback'; fallbackReason?: FallbackReason
  releaseId: string; references: SourceReference[]; followUp?: string[]; notice?: string
  candidates?: SchoolCandidate[]; coverage?: string; weakPoints?: string[]; accuracy?: number
  recordId?: number; standardAnswer?: string; userAnswer?: string; questionVersion?: number
  evidence?: AssistantEvidence[]; actions?: AssistantAction[]
  navigation?: { target: string }[]
  readScope?: string[]
  retrievalStatus?: 'READY' | 'BUILDING' | 'BUSY' | 'FAILED' | 'UNAVAILABLE'
  citationSupport?: CitationSupport
  conditions?: Record<string, unknown>
  documentProposal?: { operation: 'create' | 'update'; documentId?: string; baseVersion?: number; title: string; content: string }
}

export interface Document {
  id: number
  title: string
  subject: string
  content: string
  sourceUrl?: string
  status: 'DRAFT' | 'PENDING_REVIEW' | 'PUBLISHED' | 'REJECTED'
  createdAt: string
}

export interface School {
  id: number
  name: string
  province?: string
  level?: string
}

export interface SchoolDetail {
  id: number
  schoolId: number
  majorName: string
  majorCode?: string
  year: number
  enrollmentCount?: number
  scoreLine?: number
  remark?: string
  admissionMetrics?: AdmissionMetrics
}

export interface SchoolWarning {
  code: string
  detailId?: number | null
  metricType?: string | null
  message: string
}

export interface SchoolCatalog {
  school: School | null
  targetYear: number | null
  availableYears: number[]
  details: SchoolDetail[]
  total: number
  warnings: SchoolWarning[]
}

export interface AdmissionMetricSource {
  title: string
  url: string
  locator: string
  retrievedAt: string
  sourceType: 'OFFICIAL' | 'THIRD_PARTY'
}

export interface AdmissionMetric {
  year: number | null
  value: number | null
  status: 'OFFICIAL' | 'UNVERIFIED' | 'NOT_PUBLISHED' | 'NOT_FOUND' | 'SCOPE_MISMATCH' | 'CONFLICT'
  scopeKey: string
  scopeLabel: string
  basis: 'ORDINARY_EXAM' | 'TOTAL_INCLUDING_RECOMMENDED' | 'TOTAL_UNSPECIFIED' | 'NOT_APPLICABLE'
  notice: string
  sources: AdmissionMetricSource[]
}

export interface AdmissionMetrics {
  college: string
  track: string
  studyMode: string
  admissionCategory: string
  enrollment: AdmissionMetric | null
  cutoffReference: AdmissionMetric | null
}

export interface Question {
  id: number
  subject: string
  knowledgePoint?: string
  content: string
  optionA?: string
  optionB?: string
  optionC?: string
  optionD?: string
  answer: string
  analysis?: string
  difficulty: 'EASY' | 'MEDIUM' | 'HARD'
  questionType: string
  active: number
  reviewStatus: string
}

export type StudentQuestion = Pick<Question, 'id' | 'subject' | 'knowledgePoint' | 'content' |
  'optionA' | 'optionB' | 'optionC' | 'optionD' | 'difficulty' | 'questionType'> & { version?: number }

export interface PracticeRecord {
  id: number
  sessionId: string
  questionId: number
  orderIndex: number
  userAnswer?: string
  isCorrect?: number | null
  gradingStatus?: string
  answeredAt?: string
}

export interface StudyStat {
  id: number
  userId: number
  statDate: string
  questionCount: number
  correctCount: number
  studyMinutes: number
}
