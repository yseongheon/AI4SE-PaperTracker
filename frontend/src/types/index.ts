// 与后端 Pydantic schema 对齐（CLAUDE.md 第 8 章：改接口时两边同步）
// 后端定义见 backend/app/schemas/{paper,topic,venue,stats}.py

export interface VenueBrief {
  id: number
  short_name: string
  full_name: string
}

export interface TopicBrief {
  id: number
  slug: string
  name_zh: string
}

export interface PaperListItem {
  id: number
  title: string
  authors: string[]
  venue: VenueBrief | null
  topics: TopicBrief[]
  year: number | null
  published_at: string | null
  is_ai4se_confirmed: boolean
  arxiv_url: string | null
  dblp_url: string | null
  doi: string | null
}

export interface PaperDetail extends PaperListItem {
  abstract: string | null
  summary_zh: string | null
  is_ai4se_candidate: boolean
  match_status: string
  status: string
}

export interface PaperPage {
  items: PaperListItem[]
  total: number
  page: number
  page_size: number
}

export interface PaperListParams {
  page?: number
  page_size?: number
  q?: string
  topic?: string
  venue?: string
  year?: number
  is_ai4se?: boolean
  sort?: 'newest' | 'venue'
}

export interface TopicWithCount extends TopicBrief {
  description: string | null
  paper_count: number
}

export interface VenueWithCount extends VenueBrief {
  rank: string
  paper_count: number
}

export interface TrendSeries {
  key: string
  name: string
  values: number[]
}

export interface TrendResponse {
  group_by: 'topic' | 'venue' | 'year'
  start: string | null
  end: string | null
  labels: string[]
  series: TrendSeries[]
}

export type AggregateMode = 'day' | 'week' | 'month'
