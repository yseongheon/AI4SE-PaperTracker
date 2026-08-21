<script setup lang="ts">
// M4 列表页：左侧筛选侧栏（主题/会议/年份/AI4SE/排序/阅读状态）+ el-table + 搜索 + 分页
// M6：收藏星标 / 已读淡化 / 导出筛选结果；M7：多选导出 / 作者点击 / 高级筛选
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { listTopics } from '../api/topics'
import { listVenues } from '../api/venues'
import { getTrends, getAllInstitutions } from '../api/stats'
import { exportUrl, setMark } from '../api/papers'
import { useFilterStore } from '../stores/filterStore'
import { usePaperStore } from '../stores/paperStore'
import FilterSidebar from '../components/FilterSidebar.vue'
import TopicTag from '../components/TopicTag.vue'
import type { PaperListItem, TopicWithCount, VenueWithCount } from '../types'

const route = useRoute()
const router = useRouter()
const filter = useFilterStore()
const paperStore = usePaperStore()
const { page, pageSize } = storeToRefs(filter)

const topics = ref<TopicWithCount[]>([])
const venues = ref<VenueWithCount[]>([])
const years = ref<number[]>([])
const searchText = ref(filter.q)
const selectedIds = ref<number[]>([]) // M7 多选导出
const advVisible = ref(false) // M7 高级筛选弹窗
const instOptions = ref<{ name: string; paper_count: number }[]>([]) // M12 机构自动补全数据源（机构 TOP 榜）

// M7 已应用的高级筛选摘要（field/author/年份区间/最低被引 非默认值即展示）
const advSummary = computed(() => {
  const parts: string[] = []
  if (filter.field !== 'any') {
    parts.push({ any: '标题+摘要', title: '仅标题', abstract: '仅摘要' }[filter.field])
  }
  if (filter.author) parts.push(`作者=${filter.author}`)
  if (filter.institution) parts.push(`机构=${filter.institution}`)
  if (filter.yearFrom != null || filter.yearTo != null) {
    parts.push(`年份 ${filter.yearFrom ?? '…'}-${filter.yearTo ?? '…'}`)
  }
  if (filter.minCitations != null) parts.push(`被引≥${filter.minCitations}`)
  return parts
})

// 应用高级筛选：关弹窗 + 回到第一页（v-model 已直接写入 store，watch 自动触发请求）
function applyAdvFilter() {
  advVisible.value = false
  filter.page = 1
}

// 清除高级筛选（保留搜索词与侧栏条件）
function clearAdv() {
  filter.$patch({ field: 'any', author: '', institution: '', yearFrom: null, yearTo: null, minCitations: null, page: 1 })
}

onMounted(async () => {
  // M7：从作者榜/详情页跳转过来（?author=xxx）→ 初始化作者过滤
  if (route.query.author) {
    filter.author = String(route.query.author)
  }
  // M11：从机构榜跳转过来（?institution=xxx）→ 初始化机构过滤
  if (route.query.institution) {
    filter.institution = String(route.query.institution)
  }
  // 个人画像已读/收藏跳转（?marks=read）→ 初始化阅读状态过滤
  if (route.query.marks) {
    const m = String(route.query.marks)
    if (m === 'bookmark' || m === 'read' || m === 'read_later' || m === 'unread') {
      filter.marks = m as typeof filter.marks
    }
  }
  try {
    // 年份选项来自趋势接口的年份分组（数据驱动，不硬编码）
    const [t, v, y, inst] = await Promise.all([
      listTopics(),
      listVenues(),
      getTrends('year'),
      getAllInstitutions(),
    ])
    topics.value = t
    venues.value = v
    years.value = y.labels.map(Number)
    instOptions.value = inst.map((s) => ({ name: s.name, paper_count: s.paper_count }))
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

// M6 收藏星标：toggle 后刷新列表（marks 过滤下即时移除/恢复行）
async function toggleBookmark(row: PaperListItem) {
  try {
    await setMark(row.id, 'bookmark', !row.marks.bookmark)
    paperStore.fetch()
  } catch (e) {
    console.error('收藏失败', e)
  }
}

// M6 已读行淡化
function rowClass({ row }: { row: PaperListItem }) {
  return row.marks.read ? 'row-read' : ''
}

// 触发下载：用隐藏 <a> 点击而不是 window.open——
// 下拉菜单 @command 回调里 window.open 会被弹窗拦截（异步回调不算用户手势），导致"按了没反应"
function triggerDownload(url: string) {
  const a = document.createElement('a')
  a.href = url
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

// M6 导出当前筛选结果（浏览器直接下载）
function downloadExport(format: 'csv' | 'json' | 'bibtex') {
  ElMessage.success(`正在导出 ${format.toUpperCase()}，请查看浏览器下载栏`)
  triggerDownload(
    exportUrl(format, {
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
      institution: filter.institution || undefined,
    }),
  )
}

// M7 导出选中（勾选行）
function exportSelected(format: 'csv' | 'json' | 'bibtex') {
  if (!selectedIds.value.length) return
  ElMessage.success(`正在导出 ${selectedIds.value.length} 篇为 ${format.toUpperCase()}`)
  triggerDownload(exportUrl(format, { ids: selectedIds.value }))
}

function onSelectionChange(rows: PaperListItem[]) {
  selectedIds.value = rows.map((r) => r.id)
}

// M7 作者点击 → 按作者过滤
function filterByAuthor(name: string) {
  filter.author = name
  filter.page = 1
}

// M12 机构自动补全：从机构 TOP 榜按输入过滤（机构是精确全串匹配，下拉选才能保证命中）
function queryInstitutions(
  query: string,
  cb: (items: { value: string; paper_count: number }[]) => void,
) {
  const q = query.trim().toLowerCase()
  cb(
    instOptions.value
      .filter((s) => s.name.toLowerCase().includes(q))
      .slice(0, 20)
      .map((s) => ({ value: s.name, paper_count: s.paper_count })),
  )
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
        <el-button @click="advVisible = true">
          高级筛选<el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <!-- tooltip 必须放在 dropdown 外层：嵌套在触发器内会让下拉菜单点不开（Element Plus 已知问题） -->
        <el-tooltip content="导出符合当前筛选条件的全部论文（不勾选也有效）" placement="top">
          <el-dropdown trigger="click" @command="downloadExport">
            <el-button>
              导出筛选结果<el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="csv">CSV（Excel）</el-dropdown-item>
                <el-dropdown-item command="json">JSON</el-dropdown-item>
                <el-dropdown-item command="bibtex">BibTeX（引用）</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </el-tooltip>
        <el-tooltip content="导出当前勾选的论文（先勾选左侧 ☑ 框）" placement="top">
          <el-dropdown
            trigger="click"
            :disabled="!selectedIds.length"
            @command="exportSelected"
          >
            <el-button :disabled="!selectedIds.length">
              导出选中 ({{ selectedIds.length }})<el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="csv">CSV（Excel）</el-dropdown-item>
                <el-dropdown-item command="json">JSON</el-dropdown-item>
                <el-dropdown-item command="bibtex">BibTeX（引用）</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </el-tooltip>
        <span class="total">共 <span class="mono">{{ paperStore.total }}</span> 篇</span>
      </div>

      <!-- M7 高级筛选：dialog 弹窗（popover+tooltip 嵌套在部分环境点不开，改 dialog 更稳、手机端友好） -->
      <el-dialog v-model="advVisible" title="高级筛选" width="420px">
        <div class="adv-filter">
          <div class="adv-row">
            <span class="adv-label">搜索范围</span>
            <el-radio-group v-model="filter.field">
              <el-radio-button value="any">标题+摘要</el-radio-button>
              <el-radio-button value="title">仅标题</el-radio-button>
              <el-radio-button value="abstract">仅摘要</el-radio-button>
            </el-radio-group>
          </div>
          <div class="adv-row">
            <span class="adv-label">作者</span>
            <el-input
              v-model="filter.author"
              placeholder="作者姓名（模糊匹配）"
              clearable
              @keyup.enter="applyAdvFilter"
            />
          </div>
          <div class="adv-row">
            <span class="adv-label">机构</span>
            <el-autocomplete
              v-model="filter.institution"
              class="inst-input"
              :fetch-suggestions="queryInstitutions"
              placeholder="机构名称（精确匹配，从下拉选择）"
              clearable
              @select="applyAdvFilter"
              @keyup.enter="applyAdvFilter"
            >
              <template #default="{ item }">
                <span>{{ item.value }}</span>
                <span
                  class="inst-count"
                  style="color: var(--el-text-color-secondary); font-size: 12px; margin-left: 6px"
                >（{{ item.paper_count }} 篇）</span>
              </template>
            </el-autocomplete>
          </div>
          <div class="adv-row">
            <span class="adv-label">年份区间</span>
            <el-input-number v-model="filter.yearFrom" :min="1990" :max="2100" :controls="false" placeholder="起" style="width: 120px" />
            <span class="adv-sep">—</span>
            <el-input-number v-model="filter.yearTo" :min="1990" :max="2100" :controls="false" placeholder="止" style="width: 120px" />
          </div>
          <div class="adv-row">
            <span class="adv-label">最低被引</span>
            <el-input-number
              v-model="filter.minCitations"
              :min="0"
              :controls="false"
              placeholder="只看被引 ≥ N 的论文"
              style="width: 180px"
            />
          </div>
        </div>
        <template #footer>
          <el-button @click="filter.reset()">重置全部</el-button>
          <el-button type="primary" @click="applyAdvFilter">应用</el-button>
        </template>
      </el-dialog>

      <!-- 已应用的高级筛选条件摘要（一眼可见生效状态） -->
      <div v-if="advSummary.length" class="adv-summary">
        已应用：{{ advSummary.join(' · ') }}
        <el-link type="primary" @click="clearAdv">清除高级筛选</el-link>
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
        :row-class-name="rowClass"
        @row-click="(row: PaperListItem) => goDetail(row.id)"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="40" align="center">
          <template #header>
            <el-tooltip content="勾选多篇后，点「导出选中」批量导出" placement="top">
              <span class="sel-hint">☑</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="收藏" width="64" align="center">
          <template #default="{ row }">
            <el-button
              link
              :class="row.marks.bookmark ? 'star-on' : 'star-off'"
              :title="row.marks.bookmark ? '取消收藏' : '收藏'"
              @click.stop="toggleBookmark(row)"
            >
              {{ row.marks.bookmark ? '⭐' : '☆' }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="360">
          <template #default="{ row }">
            <el-link type="primary" @click.stop="goDetail(row.id)">{{ row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="作者" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link
              v-for="(a, i) in row.authors"
              :key="i"
              type="primary"
              class="author-link"
              @click.stop="filterByAuthor(a)"
            >
              {{ a }}<span v-if="i < row.authors.length - 1">、</span>
            </el-link>
          </template>
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
        <el-table-column label="被引" width="80" align="center">
          <template #header>
            <el-tooltip content="被引次数（Crossref / Semantic Scholar 双源）" placement="top">
              <span>被引</span>
            </el-tooltip>
          </template>
          <template #default="{ row }">
            <el-tooltip
              v-if="row.citation_count != null"
              :content="`被引 ${row.citation_count} 次（Crossref / Semantic Scholar）`"
              placement="top"
            >
              <span class="cite">🔥 {{ row.citation_count }}</span>
            </el-tooltip>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
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
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.total :deep(.mono) {
  font-weight: 700;
  color: var(--brand-text);
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
  color: var(--el-text-color-placeholder);
}
/* M7 高级筛选弹层 */
.adv-filter {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.adv-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.adv-label {
  width: 56px;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.adv-sep {
  color: var(--el-text-color-placeholder);
}
.inst-input {
  flex: 1;
}
.adv-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.adv-summary {
  margin: -6px 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
}
.author-link {
  text-decoration-thickness: 1px;
  font-weight: 500;
}
/* M6 已读行淡化（row-class-name 作用在 tr 上） */
.table :deep(tr.row-read) {
  opacity: 0.55;
}
.table :deep(tr.row-read .el-link) {
  text-decoration-color: transparent;
}
.star-on {
  font-size: 16px;
}
.star-off {
  font-size: 16px;
  opacity: 0.55;
}
.star-off:hover {
  opacity: 1;
}
.cite {
  font-size: 12px;
  color: var(--brand-text);
}
.sel-hint {
  cursor: help;
  color: var(--el-text-color-secondary);
}
.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
</style>
