// 与后端 Pydantic schema 对齐（CLAUDE.md 第 8 章：改接口时两边同步）
// 后端定义见 backend/app/schemas/{paper,topic,venue,stats}.py

export interface VenueBrief {
  id: number
  short_name: string
  full_name: string
  type: string | null // conference/journal
}

export interface TopicBrief {
  id: number
  slug: string
  name_zh: string
}

// M6 个性化阅读标记：收藏 / 已读 / 稍后读
export interface PaperMarks {
  bookmark: boolean
  read: boolean
  read_later: boolean
}

// M6 LLM 亮点速读：一句话核心贡献 + 一句话局限
export interface Highlights {
  contribution: string | null
  limitation: string | null
}

export type MarkType = 'bookmark' | 'read' | 'read_later'
export type MarksFilter = '' | 'bookmark' | 'read_later' | 'unread'

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
  marks: PaperMarks
}

export interface PaperDetail extends PaperListItem {
  abstract: string | null
  summary_zh: string | null
  highlights: Highlights | null
  is_ai4se_candidate: boolean
  match_status: string
  status: string
  related: PaperListItem[]
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
  marks?: Exclude<MarksFilter, ''>
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
