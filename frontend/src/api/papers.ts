import http from './http'
import type { MarkType, PaperDetail, PaperListParams, PaperMarks, PaperPage } from '../types'

// 论文列表：分页 + 搜索 + 主题/会议/年份/AI4SE/标记过滤 + 排序
export async function listPapers(params: PaperListParams = {}): Promise<PaperPage> {
  const { data } = await http.get<PaperPage>('/papers', { params })
  return data
}

export async function getPaper(id: number): Promise<PaperDetail> {
  const { data } = await http.get<PaperDetail>(`/papers/${id}`)
  return data
}

// M6 个性化标记：设置/取消（幂等），返回最新标记集合
export async function setMark(id: number, type: MarkType, value: boolean): Promise<PaperMarks> {
  const { data } = await http.post<PaperMarks>(`/papers/${id}/marks`, { type, value })
  return data
}

// M6 导出下载 URL（携带当前筛选条件；浏览器直接打开即下载）
export function exportUrl(
  format: 'csv' | 'json' | 'bibtex',
  params: PaperListParams,
): string {
  const sp = new URLSearchParams({ format })
  if (params.q) sp.set('q', params.q)
  if (params.topic) sp.set('topic', params.topic)
  if (params.venue) sp.set('venue', params.venue)
  if (params.year != null) sp.set('year', String(params.year))
  if (params.is_ai4se) sp.set('is_ai4se', 'true')
  if (params.marks) sp.set('marks', params.marks)
  return `/export?${sp.toString()}`
}
