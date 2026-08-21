<script setup lang="ts">
// M14 作者榜独立页（自趋势页抽出，与论文列表/机构榜/个人画像并列）：TOP 50/100/全部 + 服务端分页 + 搜索防抖
import { onMounted, ref, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAuthorsTop } from '../api/stats'
import type { AuthorStat } from '../types'

const router = useRouter()
const PAGE_SIZE = 20
const topLimit = ref<number | 'all'>('all')
const page = ref(1)
const total = ref(0)
const items = ref<AuthorStat[]>([])
const search = ref('')
const loading = ref(true)

// 搜索防抖：输入变化 300ms 后重查到第 1 页
function watchDebounced(source: Ref<string>, onFire: () => void): void {
  let timer: ReturnType<typeof setTimeout> | undefined
  watch(source, () => {
    clearTimeout(timer)
    timer = setTimeout(onFire, 300)
  })
}

watchDebounced(search, () => {
  page.value = 1
  load()
})

// 当前模式对应的一页条数：搜索或「全部」→ 走分页；TOP N → 一页取完
function pageSize(): number {
  const searching = !!search.value.trim()
  return (searching || topLimit.value === 'all') ? PAGE_SIZE : topLimit.value
}

// 榜单模式切换/搜索 → 回到第 1 页重拉
async function load() {
  page.value = 1
  try {
    const p = await getAuthorsTop(1, pageSize(), search.value.trim() || undefined)
    items.value = p.items
    total.value = p.total
  } catch (e) {
    console.error('作者榜加载失败', e)
  }
}

// 全部模式/搜索：分页器翻页
async function loadPage() {
  try {
    const p = await getAuthorsTop(page.value, PAGE_SIZE, search.value.trim() || undefined)
    items.value = p.items
    total.value = p.total
  } catch (e) {
    console.error('作者榜分页加载失败', e)
  }
}

onMounted(async () => {
  await load()
  loading.value = false
})

// 作者 → 列表页按作者过滤
function goAuthor(name: string) {
  router.push({ path: '/', query: { author: name } })
}

// 作者机构 → 机构详情页（命名路由自动编码机构名）
function goInstitution(name: string) {
  router.push({ name: 'institution-detail', params: { name } })
}
</script>

<template>
  <div v-loading="loading" class="board-page">
    <div class="topbar">
      <span class="label">榜单条数</span>
      <el-select v-model="topLimit" size="small" style="width: 110px" @change="load">
        <el-option :value="50" label="TOP 50" />
        <el-option :value="100" label="TOP 100" />
        <el-option :value="'all'" label="全部" />
      </el-select>
      <el-input
        v-model="search"
        placeholder="搜索作者名"
        clearable
        size="small"
        class="search-input"
      />
    </div>
    <el-table :data="items" stripe>
      <el-table-column
        type="index"
        :index="(i: number) => (page - 1) * PAGE_SIZE + i + 1"
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
      v-if="topLimit === 'all' || search.trim()"
      class="pager"
      background
      layout="total, prev, pager, next"
      :total="total"
      :page-size="PAGE_SIZE"
      :current-page="page"
      @current-change="(p: number) => { page = p; loadPage() }"
    />
  </div>
</template>

<style scoped>
.board-page {
  padding: 16px 20px;
}
.topbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.search-input {
  width: 240px;
  margin-left: auto;
}
.label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.topic-tag {
  margin: 2px 4px 2px 0;
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
