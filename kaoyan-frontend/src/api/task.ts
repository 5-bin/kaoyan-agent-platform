import request from './request'
import type { PageResult, Task } from '@/types/api'

export const submitTask = (data: { taskType: string; input: Record<string, unknown> }) =>
  request.post<unknown, Task>('/tasks', data)

export const getTaskList = (params: { pageNum: number; pageSize: number }) =>
  request.get<unknown, PageResult<Task>>('/tasks', { params })

export const getTaskDetail = (taskId: string) =>
  request.get<unknown, Task>(`/tasks/${taskId}`)
