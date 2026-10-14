import request from './request'

export interface LoginResult {
  accessToken: string
  refreshToken?: string
}

export const login = (data: { username: string; password: string }) =>
  request.post<unknown, LoginResult>('/auth/login', data)

export const register = (data: { username: string; password: string }) =>
  request.post('/auth/register', data)

export const refresh = (refreshToken: string) =>
  request.post<unknown, LoginResult>('/auth/refresh', { refreshToken })

export const logout = () => request.post('/auth/logout')
