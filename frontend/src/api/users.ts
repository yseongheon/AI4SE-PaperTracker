import http from './http'
import type { ProfileStats, UserInfo } from '../types'

// M9 个人画像（需登录）
export async function getProfile(): Promise<ProfileStats> {
  const { data } = await http.get<ProfileStats>('/users/me/profile')
  return data
}

// M9 反馈：修改用户名/邮箱（未传字段不改）
export async function updateProfile(
  patch: { username?: string; email?: string | null },
): Promise<UserInfo> {
  const { data } = await http.patch<UserInfo>('/users/me', patch)
  return data
}

// M9 反馈：修改密码（需旧密码）
export async function updatePassword(oldPassword: string, newPassword: string): Promise<void> {
  await http.post('/users/me/password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
