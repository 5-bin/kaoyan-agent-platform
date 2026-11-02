import type { LearningGroup, LearningProfile } from '@/api/learning'

export const SAMPLE_THRESHOLD = 5

export const SUBJECTS = ['数据结构', '计算机组成原理', '操作系统', '计算机网络'] as const

export const DIFFICULTIES = [
  { key: 'EASY', label: '简单' },
  { key: 'MEDIUM', label: '适中' },
  { key: 'HARD', label: '困难' },
] as const

export type DifficultyKey = (typeof DIFFICULTIES)[number]['key']
export type MasteryBand =
  | 'undiagnosed'
  | 'insufficient'
  | 'weak'
  | 'developing'
  | 'steady'
  | 'strong'

export interface EvidenceComposition {
  independent: number
  assisted: number
  unknown: number
  total: number
}

export interface SubjectSummary {
  subject: string
  total: number
  diagnosed: number
  insufficient: number
  sufficient: number
  samples: number
  correct: number
  wrong: number
  assisted: number
  unknown: number
  weightTotal: number
  weightCovered: number
  coverage: number
  weakest: LearningGroup | null
}

export interface HeatmapCell {
  difficulty: DifficultyKey
  label: string
  group: LearningGroup | null
}

export interface HeatmapRow {
  point: string
  priority: number
  cells: HeatmapCell[]
}

export interface HistoryPoint {
  revision: number
  label: string
  score: number | null
  coverage: number
  updatedAt: string
}

const SUBJECT_COLORS: Record<string, string> = {
  数据结构: '#3b6cff',
  计算机组成原理: '#7c5cff',
  操作系统: '#0f9d8a',
  计算机网络: '#d97706',
}

const BAND_COLORS: Record<MasteryBand, string> = {
  undiagnosed: '#eef0f3',
  insufficient: '#e5e8ee',
  weak: '#f3b6b6',
  developing: '#f6c177',
  steady: '#8fb8f7',
  strong: '#7fcf9b',
}

const BAND_LABELS: Record<MasteryBand, string> = {
  undiagnosed: '未诊断',
  insufficient: '样本不足',
  weak: '待巩固',
  developing: '有基础',
  steady: '较稳',
  strong: '优势',
}

export function subjectColor(subject: string): string {
  return SUBJECT_COLORS[subject] ?? '#64748b'
}

export function difficultyLabel(difficulty: string): string {
  return DIFFICULTIES.find(item => item.key === difficulty)?.label ?? difficulty
}

export function masteryPercent(group: LearningGroup): number | null {
  if (group.masteryIndex == null || !Number.isFinite(group.masteryIndex)) return null
  return Math.round(Math.min(1, Math.max(0, group.masteryIndex)) * 100)
}

export function masteryBand(group: LearningGroup): MasteryBand {
  if (group.samples <= 0 || group.masteryIndex == null) return 'undiagnosed'
  if (group.samples < SAMPLE_THRESHOLD) return 'insufficient'
  const mastery = Math.min(1, Math.max(0, group.masteryIndex))
  if (mastery < 0.4) return 'weak'
  if (mastery < 0.6) return 'developing'
  if (mastery < 0.8) return 'steady'
  return 'strong'
}

export function bandLabel(band: MasteryBand): string {
  return BAND_LABELS[band]
}

export function bandColor(band: MasteryBand): string {
  return BAND_COLORS[band]
}

export function groupPriority(group: LearningGroup): number {
  if (group.priority != null && Number.isFinite(group.priority)) return group.priority
  const mastery = group.masteryIndex ?? 0
  return Math.max(0, group.weight ?? 0) * (1 - Math.min(1, Math.max(0, mastery)))
}

export function topWeakPoints(groups: LearningGroup[], limit = 6): LearningGroup[] {
  return groups
    .filter(group => group.samples >= SAMPLE_THRESHOLD && group.masteryIndex != null)
    .slice()
    .sort((left, right) => {
      const priority = groupPriority(right) - groupPriority(left)
      if (priority !== 0) return priority
      const mastery = (left.masteryIndex ?? 0) - (right.masteryIndex ?? 0)
      if (mastery !== 0) return mastery
      return right.samples - left.samples
    })
    .slice(0, limit)
}

export function pendingPoints(groups: LearningGroup[], limit = 4): LearningGroup[] {
  return groups
    .filter(group => group.samples < SAMPLE_THRESHOLD)
    .slice()
    .sort((left, right) => {
      const leftStarted = left.samples > 0 ? 0 : 1
      const rightStarted = right.samples > 0 ? 0 : 1
      if (leftStarted !== rightStarted) return leftStarted - rightStarted
      const weight = Math.max(0, right.weight ?? 0) - Math.max(0, left.weight ?? 0)
      if (weight !== 0) return weight
      return left.knowledgePoint.localeCompare(right.knowledgePoint, 'zh-Hans-CN')
    })
    .slice(0, limit)
}

export function evidenceComposition(profile: LearningProfile): EvidenceComposition {
  const groups = profile.groups ?? []
  const independent = profile.independentSamples ?? groups.reduce((sum, group) => sum + group.samples, 0)
  const assisted = profile.assistedSamples ?? groups.reduce((sum, group) => sum + group.assisted, 0)
  const unknown = profile.unknownSamples ?? groups.reduce((sum, group) => sum + group.unknown, 0)
  return { independent, assisted, unknown, total: independent + assisted + unknown }
}

export function coveragePercent(profile: LearningProfile): number {
  if (!Number.isFinite(profile.coverage)) return 0
  return Math.round(Math.min(1, Math.max(0, profile.coverage)) * 100)
}

export function profileStatusLabel(profile: LearningProfile): string {
  return profile.status === 'NOT_DIAGNOSED' || !profile.independentSamples ? '尚未诊断' : '已建立画像'
}

export function subjectSummaries(groups: LearningGroup[]): SubjectSummary[] {
  const subjects = [...new Set(groups.map(group => group.subject))]
  subjects.sort((left, right) => {
    const leftIndex = SUBJECTS.indexOf(left as (typeof SUBJECTS)[number])
    const rightIndex = SUBJECTS.indexOf(right as (typeof SUBJECTS)[number])
    if (leftIndex !== rightIndex) return (leftIndex < 0 ? 99 : leftIndex) - (rightIndex < 0 ? 99 : rightIndex)
    return left.localeCompare(right, 'zh-Hans-CN')
  })
  return subjects.map(subject => {
    const rows = groups.filter(group => group.subject === subject)
    const samples = rows.reduce((sum, group) => sum + group.samples, 0)
    const correct = rows.reduce((sum, group) => sum + group.correct, 0)
    const assisted = rows.reduce((sum, group) => sum + group.assisted, 0)
    const unknown = rows.reduce((sum, group) => sum + group.unknown, 0)
    const weightTotal = rows.reduce((sum, group) => sum + Math.max(0, group.weight ?? 0), 0)
    const weightCovered = rows
      .filter(group => group.samples > 0)
      .reduce((sum, group) => sum + Math.max(0, group.weight ?? 0), 0)
    return {
      subject,
      total: rows.length,
      diagnosed: rows.filter(group => group.samples > 0).length,
      insufficient: rows.filter(group => group.samples < SAMPLE_THRESHOLD).length,
      sufficient: rows.filter(group => group.samples >= SAMPLE_THRESHOLD).length,
      samples,
      correct: Math.min(correct, samples),
      wrong: Math.max(0, samples - correct),
      assisted,
      unknown,
      weightTotal,
      weightCovered,
      coverage: weightTotal > 0 ? weightCovered / weightTotal : 0,
      weakest:
        rows
          .filter(
            group =>
              group.samples >= SAMPLE_THRESHOLD &&
              group.masteryIndex != null &&
              group.masteryIndex < 0.8,
          )
          .sort((left, right) => (left.masteryIndex ?? 0) - (right.masteryIndex ?? 0))[0] ?? null,
    }
  })
}

export function buildHeatmapRows(
  groups: LearningGroup[],
  subject: string,
  limit = 12,
): { rows: HeatmapRow[]; total: number; truncated: number } {
  const scoped = subject === '全部' ? groups : groups.filter(group => group.subject === subject)
  const byPoint = new Map<string, LearningGroup[]>()
  for (const group of scoped) {
    const rows = byPoint.get(group.knowledgePoint) ?? []
    rows.push(group)
    byPoint.set(group.knowledgePoint, rows)
  }
  const allRows: HeatmapRow[] = [...byPoint.entries()]
    .map(([point, rows]) => ({
      point,
      priority: Math.max(...rows.map(groupPriority)),
      cells: DIFFICULTIES.map(difficulty => ({
        difficulty: difficulty.key,
        label: difficulty.label,
        group: rows.find(group => group.difficulty === difficulty.key) ?? null,
      })),
    }))
    .sort((left, right) => {
      if (right.priority !== left.priority) return right.priority - left.priority
      return left.point.localeCompare(right.point, 'zh-Hans-CN')
    })
  return {
    rows: allRows.slice(0, limit),
    total: allRows.length,
    truncated: Math.max(0, allRows.length - limit),
  }
}

export function buildHistoryPoints(history: LearningProfile[]): HistoryPoint[] {
  const byRevision = new Map<number, LearningProfile>()
  for (const profile of history) {
    if (Number.isFinite(profile.revision)) byRevision.set(profile.revision, profile)
  }
  return [...byRevision.values()]
    .sort((left, right) => left.revision - right.revision)
    .map(profile => ({
      revision: profile.revision,
      label: `v${profile.revision}`,
      score: profile.referenceScore,
      coverage: Math.min(1, Math.max(0, profile.coverage ?? 0)),
      updatedAt: profile.updatedAt ?? '',
    }))
}

export function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function formatDateTime(value?: string): string {
  if (!value) return '更新时间未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
