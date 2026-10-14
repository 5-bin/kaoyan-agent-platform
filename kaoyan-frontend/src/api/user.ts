import request from './request'
import type { User } from '@/types/api'

export const getCurrentUser = () => request.get<unknown, User>('/users/me')

export const updateAvatar = (data: { avatarUrl: string }) =>
  request.put('/users/avatar', data)

export const updateProfile = (data: {
  targetSchool?: string
  targetMajor?: string
  examYear?: number
  background?: string
}) => request.put('/users/profile', data)
