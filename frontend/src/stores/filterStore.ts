import { defineStore } from 'pinia'
import type { MarksFilter } from '../types'

// 筛选条件（列表页 + 侧栏共享；paperStore 按此请求 /api/papers）
export type SortMode = 'newest' | 'venue'
export type SearchField = 'any' | 'title' | 'abstract'

export const useFilterStore = defineStore('filter', {
  state: () => ({
    page: 1,
    pageSize: 20,
    q: '', // 搜索词（回车/搜索按钮确认后写入）
    field: 'any' as SearchField, // M7 搜索范围：any=标题+摘要 / title / abstract
    topic: '', // '' = 全部
    venue: '', // '' = 全部
    year: null as number | null, // null = 全部
    yearFrom: null as number | null, // M7 年份区间起
    yearTo: null as number | null, // M7 年份区间止
    isAi4se: false, // 仅看已确认 AI4SE
    marks: '' as MarksFilter, // M6 阅读状态：'' 全部 / bookmark 收藏 / read_later 稍后读 / unread 未读
    author: '', // M7 作者过滤（作者榜/详情页点击跳转）
    sort: 'newest' as SortMode,
  }),
  actions: {
    reset() {
      this.$patch({
        page: 1,
        q: '',
        field: 'any',
        topic: '',
        venue: '',
        year: null,
        yearFrom: null,
        yearTo: null,
        isAi4se: false,
        marks: '',
        author: '',
        sort: 'newest',
      })
    },
  },
})
