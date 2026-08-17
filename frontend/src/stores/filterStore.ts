import { defineStore } from 'pinia'

// 筛选条件（列表页 + 侧栏共享；paperStore 按此请求 /api/papers）
export type SortMode = 'newest' | 'venue'

export const useFilterStore = defineStore('filter', {
  state: () => ({
    page: 1,
    pageSize: 20,
    q: '', // 搜索词（回车/搜索按钮确认后写入）
    topic: '', // '' = 全部
    venue: '', // '' = 全部
    year: null as number | null, // null = 全部
    isAi4se: false, // 仅看已确认 AI4SE
    sort: 'newest' as SortMode,
  }),
  actions: {
    reset() {
      this.$patch({
        page: 1,
        q: '',
        topic: '',
        venue: '',
        year: null,
        isAi4se: false,
        sort: 'newest',
      })
    },
  },
})
