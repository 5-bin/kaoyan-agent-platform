import { defineStore } from 'pinia'
import { login as apiLogin, register as apiRegister, logout as apiLogout } from '@/api/auth'
import { getCurrentUser, getAvatarContent } from '@/api/user'
import type { User } from '@/types/api'

interface UserState {
  token: string
  refreshToken: string
  userInfo: User | null
  avatarDisplayUrl: string
}

function readCachedUser(): User | null {
  try { return JSON.parse(localStorage.getItem('userInfo') || 'null') }
  catch { return null }
}

export const useUserStore = defineStore('user', {
  state: (): UserState => ({
    token: localStorage.getItem('token') || '',
    refreshToken: localStorage.getItem('refreshToken') || '',
    userInfo: readCachedUser(),
    avatarDisplayUrl: ''
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
      await this.refreshAvatar()
    },
    async refreshAvatar() {
      const token = this.token
      if (!token || !this.userInfo?.avatarUrl) return
      try {
        const blob = await getAvatarContent()
        if (this.token !== token) return
        if (this.avatarDisplayUrl) URL.revokeObjectURL(this.avatarDisplayUrl)
        this.avatarDisplayUrl = URL.createObjectURL(blob)
      } catch {
        if (this.token === token && this.avatarDisplayUrl) {
          URL.revokeObjectURL(this.avatarDisplayUrl)
          this.avatarDisplayUrl = ''
        }
      }
    },
    setUserInfo(u: User) {
      this.userInfo = u
      localStorage.setItem('userInfo', JSON.stringify(u))
    },
    async logout() {
      const token = this.token
      try { if (token) await apiLogout() }
      finally { if (token === this.token) this.clearSession() }
    },
    clearSession() {
      if (this.avatarDisplayUrl) URL.revokeObjectURL(this.avatarDisplayUrl)
      this.avatarDisplayUrl = ''
      this.token = ''
      this.refreshToken = ''
      this.userInfo = null
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
      localStorage.removeItem('userInfo')
    }
  }
})
