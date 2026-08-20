import http from './http'
import type {
  AuthorStat, CoauthorGraph, CrossMatrix, InstitutionDetail, InstitutionStat,
  TrendResponse, WordItem,
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

export async function getAuthorsTop(limit = 50): Promise<AuthorStat[]> {
  const { data } = await http.get<{ authors: AuthorStat[] }>('/stats/authors', {
    params: { limit },
  })
  return data.authors
}

export async function getInstitutionsTop(limit = 50): Promise<InstitutionStat[]> {
  const { data } = await http.get<{ institutions: InstitutionStat[] }>('/stats/institutions', {
    params: { limit },
  })
  return data.institutions
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
