import registry from '../../../config/assistant-navigation.json'
import type { TaskResult } from '@/types/api'

export const navigationDestinations = registry
export function navigationPath(target: string) { return registry.find(item => item.target === target)?.path }

/** Also derives destinations for old results; never trusts an arbitrary URL. */
export function resultNavigation(result: TaskResult, admin: boolean) {
  const selected = new Set((result.navigation || []).map(item => item.target))
  const answer = result.answer || ''
  for (const item of registry) if (item.aliases.some(alias => answer.includes(alias))) selected.add(item.target)
  if (result.documentProposal) selected.add('NOTES')
  if (result.candidates?.length) selected.add('SCHOOLS')
  for (const item of result.evidence || []) {
    const resourceTargets: Record<string, string> = { question: 'PRACTICE', practice: 'PRACTICE', document: 'DOCUMENTS', stats: 'STATS' }
    const target = resourceTargets[item.resource?.type || '']
    if (target) selected.add(target)
  }
  const readTargets: Record<string, string> = { wrong: 'WRONG', favorite: 'FAVORITE', stats: 'STATS', practice: 'PRACTICE', questions: 'PRACTICE', documents: 'DOCUMENTS' }
  for (const scope of result.readScope || []) if (readTargets[scope]) selected.add(readTargets[scope])
  const actionTargets: Record<string, string> = { PRACTICE_CREATE: 'PRACTICE', FAVORITE_ADD: 'FAVORITE', FAVORITE_REMOVE: 'FAVORITE', WRONG_REMOVE: 'WRONG' }
  for (const action of result.actions || []) if (actionTargets[action.type]) selected.add(actionTargets[action.type])
  return registry.filter(item => selected.has(item.target) && (!item.admin || admin))
}
