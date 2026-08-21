<script setup lang="ts">
// M13 作者·机构榜（自趋势页抽出为独立页）：TOP 50/100/全部 + 双榜服务端分页 + 搜索防抖
import { onMounted, ref, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAuthorsTop, getInstitutionsTop } from '../api/stats'
import type { AuthorStat, InstitutionStat } from '../types'

const router = useRouter()
// M13 榜单模式：TOP 50 / TOP 100 / 全部（默认全部，服务端分页）；每个榜单独立分页状态
const PAGE_SIZE = 20
const topLimit = ref<number | 'all'>('all')
const authorPage = ref(1)
const instPage = ref(1)
const authorTotal = ref(0)
const instTotal = ref(0)

// 搜索防抖：输入变化 300ms 后执行 onFire（作者/机构榜搜索共用）
function watchDebounced(source: Ref<string>, onFire: () => void): void {
  let timer: ReturnType<typeof setTimeout> | undefined
  watch(source, () => {
    clearTimeout(timer)
    timer = setTimeout(onFire, 300)
  })
}

// 作者/机构榜搜索：输入变化后重置到第 1 页重查
const authorSearch = ref('')
watchDebounced(authorSearch, () => {
  authorPage.value = 1
  loadAuthorBoard()
})

const instSearch = ref('')
watchDebounced(instSearch, () => {
  instPage.value = 1
  loadInstitutionBoard()
})

const authors = ref<AuthorStat[]>([])
const institutions = ref<InstitutionStat[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    await loadTops()
  } catch (e) {
    console.error('榜单数据加载失败', e)
  } finally {
    loading.value = false
  }
})

// 榜单当前模式对应的一页条数：搜索或「全部」→ 走分页；TOP N → 一页取完
function authorPageSize(): number {
  const searching = !!authorSearch.value.trim()
  return (searching || topLimit.value === 'all') ? PAGE_SIZE : topLimit.value
}

function institutionPageSize(): number {
  const searching = !!instSearch.value.trim()
  return (searching || topLimit.value === 'all') ? PAGE_SIZE : topLimit.value
}

// 榜单模式切换 → 两榜回到第 1 页重新拉取（TOP N 一页取完；全部模式走分页）
async function loadTops() {
  authorPage.value = 1
  instPage.value = 1
  try {
    const [a, i] = await Promise.all([
      getAuthorsTop(1, authorPageSize(), authorSearch.value.trim() || undefined),
      getInstitutionsTop(1, institutionPageSize(), instSearch.value.trim() || undefined),
    ])
    authors.value = a.items
    authorTotal.value = a.total
    institutions.value = i.items
    instTotal.value = i.total
  } catch (e) {
    console.error('榜单数据加载失败', e)
  }
}

// 榜单第 1 页重查（搜索输入变化时防抖触发）
async function loadAuthorBoard() {
  try {
    const p = await getAuthorsTop(1, authorPageSize(), authorSearch.value.trim() || undefined)
    authors.value = p.items
    authorTotal.value = p.total
  } catch (e) {
    console.error('作者榜加载失败', e)
  }
}

async function loadInstitutionBoard() {
  try {
    const p = await getInstitutionsTop(
      1,
      institutionPageSize(),
      instSearch.value.trim() || undefined,
    )
    institutions.value = p.items
    instTotal.value = p.total
  } catch (e) {
    console.error('机构榜加载失败', e)
  }
}

// 全部模式/搜索：两榜分页器各自翻页（互不影响）
async function loadAuthorPage() {
  try {
    const p = await getAuthorsTop(
      authorPage.value,
      PAGE_SIZE,
      authorSearch.value.trim() || undefined,
    )
    authors.value = p.items
    authorTotal.value = p.total
  } catch (e) {
    console.error('作者榜分页加载失败', e)
  }
}

async function loadInstitutionPage() {
  try {
    const p = await getInstitutionsTop(
      instPage.value,
      PAGE_SIZE,
      instSearch.value.trim() || undefined,
    )
    institutions.value = p.items
    instTotal.value = p.total
  } catch (e) {
    console.error('机构榜分页加载失败', e)
  }
}

// 作者榜 → 列表页按作者过滤
function goAuthor(name: string) {
  router.push({ path: '/', query: { author: name } })
}

// M12 机构榜/作者机构 → 机构详情页（命名路由自动编码机构名）
function goInstitution(name: string) {
  router.push({ name: 'institution-detail', params: { name } })
}
</script>

<template>
  <div v-loading="loading" class="leaderboard-page">
    <div class="topbar">
      <span class="label">榜单条数</span>
      <el-select v-model="topLimit" size="small" style="width: 110px" @change="loadTops">
        <el-option :value="50" label="TOP 50" />
        <el-option :value="100" label="TOP 100" />
        <el-option :value="'all'" label="全部" />
      </el-select>
    </div>
    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <div class="panel-head">
          <h3 class="panel-title">作者榜</h3>
          <el-input
            v-model="authorSearch"
            placeholder="搜索作者名"
            clearable
            size="small"
            style="width: 240px"
          />
        </div>
        <el-table :data="authors" stripe>
          <el-table-column
            type="index"
            :index="(i: number) => (authorPage - 1) * PAGE_SIZE + i + 1"
            label="#"
            width="64"
            align="center"
          />
          <el-table-column label="学者" min-width="160">
            <template #default="{ row }">
              <el-tooltip :content="`查看 ${row.name} 的全部论文`" placement="top">
                <el-link type="primary" @click="goAuthor(row.name)">{{ row.name }}</el-link>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="机构" min-width="150">
            <template #default="{ row }">
              <el-link
                v-if="row.affiliation"
                type="primary"
                @click="goInstitution(row.affiliation)"
              >
                {{ row.affiliation }}
              </el-link>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="paper_count" label="论文数" width="88" align="center" />
          <el-table-column prop="ai4se_count" label="AI4SE" width="88" align="center" />
          <el-table-column label="主要主题" min-width="200">
            <template #default="{ row }">
              <el-tag
                v-for="t in row.top_topics"
                :key="t.slug"
                size="small"
                class="topic-tag"
              >
                {{ t.name_zh }} ({{ t.count }})
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-if="topLimit === 'all' || authorSearch.trim()"
          class="pager"
          background
          layout="total, prev, pager, next"
          :total="authorTotal"
          :page-size="PAGE_SIZE"
          :current-page="authorPage"
          @current-change="(p: number) => { authorPage = p; loadAuthorPage() }"
        />
      </el-col>
      <el-col :xs="24" :md="12">
        <div class="panel-head">
          <h3 class="panel-title">机构榜</h3>
          <el-input
            v-model="instSearch"
            placeholder="搜索机构名"
            clearable
            size="small"
            style="width: 240px"
          />
        </div>
        <el-table :data="institutions" stripe>
          <el-table-column
            type="index"
            :index="(i: number) => (instPage - 1) * PAGE_SIZE + i + 1"
            label="#"
            width="64"
            align="center"
          />
          <el-table-column label="机构" min-width="200">
            <template #default="{ row }">
              <el-tooltip :content="`查看 ${row.name} 的全部论文`" placement="top">
                <el-link type="primary" @click="goInstitution(row.name)">{{ row.name }}</el-link>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="paper_count" label="论文数" width="88" align="center" />
          <el-table-column prop="ai4se_count" label="AI4SE" width="88" align="center" />
          <el-table-column label="主要主题" min-width="200">
            <template #default="{ row }">
              <el-tag
                v-for="t in row.top_topics"
                :key="t.slug"
                size="small"
                class="topic-tag"
              >
                {{ t.name_zh }} ({{ t.count }})
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-if="topLimit === 'all' || instSearch.trim()"
          class="pager"
          background
          layout="total, prev, pager, next"
          :total="instTotal"
          :page-size="PAGE_SIZE"
          :current-page="instPage"
          @current-change="(p: number) => { instPage = p; loadInstitutionPage() }"
        />
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.leaderboard-page {
  padding: 16px 20px;
}
.topbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.topic-tag {
  margin: 2px 4px 2px 0;
}
.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.muted {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.pager {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}
</style>
