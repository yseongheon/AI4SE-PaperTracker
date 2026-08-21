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
export type MarksFilter = '' | 'bookmark' | 'read' | 'read_later' | 'unread'

export interface PaperListItem {
  id: number
  title: string
  authors: string[]
  venue: VenueBrief | null
  topics: TopicBrief[]
  year: number | null
  published_at: string | null
  is_ai4se_confirmed: boolean
  citation_count: number | null // M8 Crossref/S2 双源引用数
  arxiv_url: string | null
  pdf_url: string | null // M7 arXiv PDF 直链
  dblp_url: string | null
  doi: string | null
  marks: PaperMarks
}

// M12 详情页作者：姓名 + 机构（可点击跳机构详情页）
export interface AuthorBrief {
  name: string
  affiliation: string | null
}

// M12：详情作者是 AuthorBrief[]（列表仍是 string[]），必须 Omit 掉父类 authors 再覆盖
export interface PaperDetail extends Omit<PaperListItem, 'authors'> {
  authors: AuthorBrief[]
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
  field?: 'any' | 'title' | 'abstract' // M7 搜索范围
  topic?: string
  venue?: string
  year?: number
  year_from?: number // M7 年份区间
  year_to?: number
  is_ai4se?: boolean
  marks?: Exclude<MarksFilter, ''>
  author?: string // M7 作者过滤
  institution?: string // M11 机构过滤（机构榜点击跳转）
  min_citations?: number // M8 最低引用数
  sort?: 'newest' | 'venue' | 'citations'
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

// ---- M9 认证 ----

export interface UserInfo {
  id: number
  username: string
  email: string | null
}

export interface AuthResponse {
  token: string
  user: UserInfo
}

export interface ProfileStats {
  username: string
  email: string | null
  counts: { bookmark: number; read: number; read_later: number }
  topic_dist: { slug: string; name_zh: string; count: number }[]
  recent: PaperListItem[]
  recent_read: PaperListItem[] // 最近已读（画像页「最近已读」列表）
}

// ---- M7 分析图表 ----

export interface WordItem {
  word: string
  count: number
}

export interface AuthorStat {
  id: number
  name: string
  paper_count: number
  ai4se_count: number
  top_topics: { slug: string; name_zh: string; count: number }[]
  affiliation?: string | null // M11 作者出身机构（arXiv 机构，规则归一化；无则 null）
}

// M11 机构榜：机构名即 key（无 id），计数为 DISTINCT 论文数
export interface InstitutionStat {
  name: string
  paper_count: number
  ai4se_count: number
  top_topics: { slug: string; name_zh: string; count: number }[]
}

// M13 作者/机构榜分页响应（遵循后端 {items, total, page, page_size} 约定）
export interface AuthorPage {
  items: AuthorStat[]
  total: number
  page: number
  page_size: number
}

export interface InstitutionPage {
  items: InstitutionStat[]
  total: number
  page: number
  page_size: number
}

// M12 机构详情：统计 + 主题分布 + 合作机构
export interface InstitutionTopicStat {
  slug: string
  name_zh: string
  count: number
}

export interface CoInstitution {
  name: string
  count: number
}

export interface InstitutionDetail {
  name: string
  paper_count: number
  ai4se_count: number
  topics: InstitutionTopicStat[]
  co_institutions: CoInstitution[]
}

export interface CrossMatrix {
  venues: string[]
  topics: string[]
  matrix: number[][]
}

export interface CoauthorNode {
  id: number
  name: string
  paper_count: number
}

export interface CoauthorLink {
  source: number
  target: number
  weight: number
}

export interface CoauthorGraph {
  nodes: CoauthorNode[]
  links: CoauthorLink[]
}

export interface DeepSummary {
  background: string
  problem: string
  method: string
  results: string
  conclusion: string
}
