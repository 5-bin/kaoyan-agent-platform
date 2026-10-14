import { defineStore } from 'pinia'
import { login as apiLogin, register as apiRegister } from '@/api/auth'
import { getCurrentUser } from '@/api/user'
import type { User } from '@/types/api'

interface UserState {
  token: string
  refreshToken: string
  userInfo: User | null
}

export const useUserStore = defineStore('user', {
  state: (): UserState => ({
    token: localStorage.getItem('token') || '',
    refreshToken: localStorage.getItem('refreshToken') || '',
    userInfo: JSON.parse(localStorage.getItem('userInfo') || 'null')
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    isAdmin: (s) => s.userInfo?.role === 'ADMIN'
  },
  actions: {
    async login(username: string, password: string) {
      const data = await apiLogin({ username, password })
      this.token = data.accessToken
      this.refreshToken = data.refreshToken || ''
      localStorage.setItem('token', this.token)
      localStorage.setItem('refreshToken', this.refreshToken)
      await this.refreshUserInfo()
    },
    async register(username: string, password: string) {
      await apiRegister({ username, password })
      await this.login(username, password)
    },
    async refreshUserInfo() {
      if (!this.token) return
      this.userInfo = await getCurrentUser()
      localStorage.setItem('userInfo', JSON.stringify(this.userInfo))
    },
    setUserInfo(u: User) {
      this.userInfo = u
      localStorage.setItem('userInfo', JSON.stringify(u))
    },
    logout() {
      this.token = ''
      this.refreshToken = ''
      this.userInfo = null
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
      localStorage.removeItem('userInfo')
    }
  }
})
