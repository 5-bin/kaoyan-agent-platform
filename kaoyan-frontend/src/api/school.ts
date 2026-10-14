import request from './request'
import type { School, SchoolDetail } from '@/types/api'

export interface SchoolDetailVO {
  school: School
  details: SchoolDetail[]
}

export const searchSchools = (params: {
  province?: string
  level?: string
  majorName?: string
}) => request.get<unknown, School[]>('/schools', { params })

export const getSchoolDetail = (schoolId: number) =>
  request.get<unknown, SchoolDetailVO>(`/schools/${schoolId}`)
