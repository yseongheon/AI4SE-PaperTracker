<script setup lang="ts">
// M4 列表页：左侧筛选侧栏（主题/会议/年份/AI4SE/排序）+ el-table + 搜索 + 分页
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { listTopics } from '../api/topics'
import { listVenues } from '../api/venues'
import { getTrends } from '../api/stats'
import { useFilterStore } from '../stores/filterStore'
import { usePaperStore } from '../stores/paperStore'
import FilterSidebar from '../components/FilterSidebar.vue'
import TopicTag from '../components/TopicTag.vue'
import type { PaperListItem, TopicWithCount, VenueWithCount } from '../types'

const router = useRouter()
const filter = useFilterStore()
const paperStore = usePaperStore()
const { page, pageSize } = storeToRefs(filter)

const topics = ref<TopicWithCount[]>([])
const venues = ref<VenueWithCount[]>([])
const years = ref<number[]>([])
const searchText = ref(filter.q)

onMounted(async () => {
  try {
    // 年份选项来自趋势接口的年份分组（数据驱动，不硬编码）
    const [t, v, y] = await Promise.all([listTopics(), listVenues(), getTrends('year')])
    topics.value = t
    venues.value = v
    years.value = y.labels.map(Number)
  } catch (e) {
    console.error('侧栏数据加载失败', e)
  }
})

// 筛选条件变化 → 重新请求；immediate 承担初始加载
watch(
  () => filter.$state,
  () => paperStore.fetch(),
  { deep: true, immediate: true },
)

function applySearch() {
  filter.q = searchText.value.trim()
  filter.page = 1
}

function onSizeChange() {
  filter.page = 1
}

function goDetail(id: number) {
  router.push(`/papers/${id}`)
}

function authorsText(authors: string[]): string {
  return authors.length > 3
    ? authors.slice(0, 3).join(', ') + ` 等 ${authors.length} 人`
    : authors.join(', ')
}
</script>

<template>
  <div class="paper-list">
    <FilterSidebar :topics="topics" :venues="venues" :years="years" />
    <div class="main">
      <div class="toolbar">
        <el-input
          v-model="searchText"
          class="search"
          placeholder="搜索标题或摘要…"
          clearable
          @keyup.enter="applySearch"
          @clear="applySearch"
        />
        <el-button type="primary" @click="applySearch">搜索</el-button>
        <span class="total">共 {{ paperStore.total }} 篇</span>
      </div>

      <el-alert
        v-if="paperStore.error"
        :title="`加载失败：${paperStore.error}（请确认后端 8000 端口已启动）`"
        type="error"
        show-icon
        class="error"
      />

      <el-table
        :data="paperStore.items"
        v-loading="paperStore.loading"
        stripe
        class="table"
        @row-click="(row: PaperListItem) => goDetail(row.id)"
      >
        <el-table-column label="标题" min-width="360">
          <template #default="{ row }">
            <el-link type="primary" @click.stop="goDetail(row.id)">{{ row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="作者" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ authorsText(row.authors) }}</template>
        </el-table-column>
        <el-table-column label="会议" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.venue" size="small" type="warning">
              {{ row.venue.short_name }}
            </el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="年份" width="80" align="center" prop="year" />
        <el-table-column label="主题" min-width="220">
          <template #default="{ row }">
            <TopicTag v-for="t in row.topics" :key="t.slug" :topic="t" />
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="paperStore.total > 0"
        class="pager"
        background
        layout="total, sizes, prev, pager, next"
        :total="paperStore.total"
        :page-sizes="[10, 20, 50]"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        @size-change="onSizeChange"
      />
    </div>
  </div>
</template>

<style scoped>
.paper-list {
  display: flex;
  height: 100%;
}
.main {
  flex: 1;
  padding: 16px 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.search {
  width: 320px;
}
.total {
  color: #909399;
  font-size: 13px;
}
.error {
  margin-bottom: 12px;
}
.table {
  flex: 1;
}
.table :deep(.el-table__row) {
  cursor: pointer;
}
.muted {
  color: #c0c4cc;
}
.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
</style>
