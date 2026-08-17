import http from './http'
import type { TopicWithCount } from '../types'

// 主题列表（含各主题论文数），供筛选侧栏
export async function listTopics(): Promise<TopicWithCount[]> {
  const { data } = await http.get<TopicWithCount[]>('/topics')
  return data
}
