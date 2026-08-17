import axios from 'axios'

// 统一 Axios 实例（CLAUDE.md 第 8 章：baseURL=/api，Vite dev proxy 转发到后端）
const http = axios.create({ baseURL: '/api', timeout: 15000 })

http.interceptors.response.use(
  (res) => res,
  (err) => {
    console.error('[api]', err?.message)
    return Promise.reject(err)
  },
)

export default http
