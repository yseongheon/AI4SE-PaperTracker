import http from './http'
import type { TrendResponse } from '../types'

// 趋势：group_by=topic|venue|year；后端按天返回原始计数，聚合粒度由前端决定（DR-020）
export async function getTrends(
  groupBy: 'topic' | 'venue' | 'year',
  start?: string,
  end?: string,
): Promise<TrendResponse> {
  const { data } = await http.get<TrendResponse>('/stats/trends', {
    params: { group_by: groupBy, start, end },
  })
  return data
}
