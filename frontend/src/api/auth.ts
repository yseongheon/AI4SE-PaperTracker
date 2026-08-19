import http from './http'
import type { AuthResponse } from '../types'

// M9 认证：注册 / 登录（HMAC token）
export async function login(username: string, password: string): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>('/auth/login', { username, password })
  return data
}

export async function register(
  username: string,
  password: string,
  email?: string,
): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>('/auth/register', {
    username,
    password,
    email: email || null,
  })
  return data
}
