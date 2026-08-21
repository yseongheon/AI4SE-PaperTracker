import http from './http'
import type {
  AuthorPage, CoauthorGraph, CrossMatrix, InstitutionDetail, InstitutionPage,
  InstitutionStat, TrendResponse, WordItem,
} from '../types'

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

// ---- M7 分析图表 ----

export async function getWords(limit = 50, scope: 'all' | 'ai4se' = 'ai4se'): Promise<WordItem[]> {
  const { data } = await http.get<{ words: WordItem[] }>('/stats/words', {
    params: { limit, scope },
  })
  return data.words
}

// M13 作者/机构榜：服务端分页（返回 {items, total, page, page_size}）；q 按作者名模糊搜索
export async function getAuthorsTop(
  page = 1,
  pageSize = 20,
  q?: string,
): Promise<AuthorPage> {
  const { data } = await http.get<AuthorPage>('/stats/authors', {
    params: { page, page_size: pageSize, q: q || undefined },
  })
  return data
}

export async function getInstitutionsTop(
  page = 1,
  pageSize = 20,
  q?: string,
): Promise<InstitutionPage> {
  const { data } = await http.get<InstitutionPage>('/stats/institutions', {
    params: { page, page_size: pageSize, q: q || undefined },
  })
  return data
}

// PaperListView 机构自动补全数据源：分页循环取全部机构（后端 page_size 上限 100）
export async function getAllInstitutions(): Promise<InstitutionStat[]> {
  const first = await getInstitutionsTop(1, 100)
  const pages = Math.max(1, Math.ceil(first.total / 100))
  const rest = await Promise.all(
    Array.from({ length: pages - 1 }, (_, i) => getInstitutionsTop(i + 2, 100)),
  )
  return [...first.items, ...rest.flatMap((p) => p.items)]
}

// M12 机构详情：统计 + 主题分布 + 合作机构（axios 自动编码机构名）
export async function getInstitutionDetail(name: string): Promise<InstitutionDetail> {
  const { data } = await http.get<InstitutionDetail>('/stats/institution', { params: { name } })
  return data
}

export async function getCross(): Promise<CrossMatrix> {
  const { data } = await http.get<CrossMatrix>('/stats/cross')
  return data
}

export async function getCoauthor(limit = 100): Promise<CoauthorGraph> {
  const { data } = await http.get<CoauthorGraph>('/stats/coauthor', { params: { limit } })
  return data
}
