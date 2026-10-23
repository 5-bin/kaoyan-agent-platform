import request from './request'
export type PrivacyScope = 'wrong' | 'favorite' | 'stats' | 'profile' | 'document'
export interface PrivacySettings { modelAllowed: boolean; scopes: PrivacyScope[]; version: number; provider: string; retentionDays: number }
export const getPrivacySettings = () => request.get<unknown, PrivacySettings>('/privacy/settings')
export const savePrivacySettings = (data: Pick<PrivacySettings, 'modelAllowed' | 'scopes' | 'provider'>) => request.put<unknown, PrivacySettings>('/privacy/settings', data)
