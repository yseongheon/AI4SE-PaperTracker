import http from './http'
import type { DeepSummary, MarkType, PaperDetail, PaperListParams, PaperMarks, PaperPage } from '../types'

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

// M7 单篇 BibTeX 文本（复制/下载用）
export async function getBibtex(id: number): Promise<string> {
  const { data } = await http.get<string>(`/papers/${id}/bibtex`, {
    responseType: 'text',
  })
  return data
}

// M7 AI 深度摘要：按需生成 + 缓存复用（后端缓存，重复调用零成本）
export async function getDeepSummary(id: number): Promise<DeepSummary> {
  const { data } = await http.post<DeepSummary>(`/papers/${id}/deep-summary`)
  return data
}

// M6 导出下载 URL（携带当前筛选条件；浏览器直接打开即下载）
// 注意：必须带 /api 前缀——后端导出路由是 /api/export（挂在 /api 下）；缺了会命中 SPA 兜底返回首页 HTML，点按钮无下载效果
export function exportUrl(
  format: 'csv' | 'json' | 'bibtex',
  params: PaperListParams & { ids?: number[] },
): string {
  const sp = new URLSearchParams({ format })
  if (params.q) sp.set('q', params.q)
  if (params.field && params.field !== 'any') sp.set('field', params.field)
  if (params.topic) sp.set('topic', params.topic)
  if (params.venue) sp.set('venue', params.venue)
  if (params.year != null) sp.set('year', String(params.year))
  if (params.year_from != null) sp.set('year_from', String(params.year_from))
  if (params.year_to != null) sp.set('year_to', String(params.year_to))
  if (params.is_ai4se) sp.set('is_ai4se', 'true')
  if (params.marks) sp.set('marks', params.marks)
  if (params.author) sp.set('author', params.author)
  if (params.institution) sp.set('institution', params.institution)
  if (params.ids?.length) sp.set('ids', params.ids.join(','))
  return `/api/export?${sp.toString()}`
}
