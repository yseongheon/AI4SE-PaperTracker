import { defineStore } from 'pinia'
import { listPapers } from '../api/papers'
import type { PaperListItem } from '../types'
import { useFilterStore } from './filterStore'

// 论文列表数据：按 filterStore 条件请求，筛选变化由列表页统一驱动 fetch
export const usePaperStore = defineStore('paper', {
  state: () => ({
    items: [] as PaperListItem[],
    total: 0,
    loading: false,
    error: '' as string,
  }),
  actions: {
    async fetch() {
      const filter = useFilterStore()
      this.loading = true
      this.error = ''
      try {
        const page = await listPapers({
          page: filter.page,
          page_size: filter.pageSize,
          q: filter.q || undefined,
          field: filter.field,
          topic: filter.topic || undefined,
          venue: filter.venue || undefined,
          year: filter.year ?? undefined,
          year_from: filter.yearFrom ?? undefined,
          year_to: filter.yearTo ?? undefined,
          is_ai4se: filter.isAi4se || undefined,
          marks: filter.marks || undefined,
          author: filter.author || undefined,
          sort: filter.sort,
        })
        this.items = page.items
        this.total = page.total
      } catch (e) {
        this.error = e instanceof Error ? e.message : '加载失败'
      } finally {
        this.loading = false
      }
    },
  },
})
