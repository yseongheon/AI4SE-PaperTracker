import http from './http'
import type { PaperDetail, PaperListParams, PaperPage } from '../types'

// 论文列表：分页 + 搜索 + 主题/会议/年份/AI4SE 过滤 + 排序
export async function listPapers(params: PaperListParams = {}): Promise<PaperPage> {
  const { data } = await http.get<PaperPage>('/papers', { params })
  return data
}

export async function getPaper(id: number): Promise<PaperDetail> {
  const { data } = await http.get<PaperDetail>(`/papers/${id}`)
  return data
}
