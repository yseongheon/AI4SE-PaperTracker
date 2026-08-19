import http from './http'
import type { ProfileStats } from '../types'

// M9 个人画像（需登录）
export async function getProfile(): Promise<ProfileStats> {
  const { data } = await http.get<ProfileStats>('/users/me/profile')
  return data
}
