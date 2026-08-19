import { defineStore } from 'pinia'
import { login as apiLogin, register as apiRegister } from '../api/auth'
import type { UserInfo } from '../types'

// M9 登录状态：token + user，localStorage 持久化（刷新不丢）
export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('auth_token') || '',
    user: JSON.parse(localStorage.getItem('auth_user') || 'null') as UserInfo | null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
  },
  actions: {
    _persist(token: string, user: UserInfo) {
      this.token = token
      this.user = user
      localStorage.setItem('auth_token', token)
      localStorage.setItem('auth_user', JSON.stringify(user))
    },
    async login(username: string, password: string) {
      const res = await apiLogin(username, password)
      this._persist(res.token, res.user)
    },
    async register(username: string, password: string, email?: string) {
      const res = await apiRegister(username, password, email)
      this._persist(res.token, res.user)
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
    },
  },
})
