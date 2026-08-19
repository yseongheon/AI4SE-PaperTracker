import axios from 'axios'

// 统一 Axios 实例（CLAUDE.md 第 8 章：baseURL=/api，Vite dev proxy 转发到后端）
const http = axios.create({ baseURL: '/api', timeout: 15000 })

// M9：请求带 Bearer token（localStorage 持久化，刷新不丢登录）
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (res) => res,
  (err) => {
    console.error('[api]', err?.message)
    return Promise.reject(err)
  },
)

export default http
