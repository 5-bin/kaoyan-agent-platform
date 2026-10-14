import axios, { type AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import router from '@/router'

const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 55000
})

request.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => {
    const sent = response.config.headers.Authorization
    const current = useUserStore().token
    if (sent && sent !== `Bearer ${current}`) return Promise.reject(new Error('SESSION_CHANGED'))
    const res = response.data
    if (res.code === 0) {
      return res.data
    }
    ElMessage.error(res.message || '请求失败')
    return Promise.reject(new Error(res.message || 'Error'))
  },
  (error) => {
    const status = error.response?.status
    const sent = error.config?.headers?.Authorization
    if (sent && sent !== `Bearer ${useUserStore().token}`) return Promise.reject(new Error('SESSION_CHANGED'))
    if (status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      router.push('/login')
      ElMessage.error('登录已过期，请重新登录')
    } else if (status === 403) {
      ElMessage.error('无权访问')
    } else {
      ElMessage.error(error.code === 'ECONNABORTED'
        ? '等待超时，任务可能仍在处理。请先查看任务历史，避免重复提交。'
        : error.response?.data?.message || '网络异常')
    }
    return Promise.reject(error)
  }
)

export default request
