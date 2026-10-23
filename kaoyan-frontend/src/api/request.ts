import axios, { type AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import router from '@/router'

declare module 'axios' {
  interface InternalAxiosRequestConfig { sessionToken?: string }
}

const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 55000
})

// Shared by Axios requests and Bearer-authenticated fetch streams.
export function handleAuthFailure(status: number | undefined, token: string) {
  if (token !== useUserStore().token) throw new axios.CanceledError('账号已切换，忽略旧请求')
  if (status === 401) {
    useUserStore().clearSession()
    void router.push('/login')
    ElMessage.error('登录已过期，请重新登录')
    return true
  }
  if (status === 403) { ElMessage.error('无权访问'); return true }
  return false
}

request.interceptors.request.use((config) => {
  const userStore = useUserStore()
  config.sessionToken = userStore.token
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => {
    if (response.config.sessionToken !== useUserStore().token) {
      return Promise.reject(new axios.CanceledError('账号已切换，忽略旧请求'))
    }
    const res = response.data
    if (res.code === 0) {
      return res.data
    }
    ElMessage.error(res.message || '请求失败')
    return Promise.reject(new Error(res.message || 'Error'))
  },
  (error) => {
    if (error.config && error.config.sessionToken !== useUserStore().token) {
      return Promise.reject(new axios.CanceledError('账号已切换，忽略旧请求'))
    }
    const status = error.response?.status
    if (handleAuthFailure(status, error.config?.sessionToken ?? useUserStore().token)) {
      return Promise.reject(error)
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('等待超时，任务可能仍在处理，请先查看任务记录，避免重复提交')
    } else {
      ElMessage.error(error.response?.data?.message || '网络异常')
    }
    return Promise.reject(error)
  }
)

export default request
