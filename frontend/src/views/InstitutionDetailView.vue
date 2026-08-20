<script setup lang="ts">
// M12 机构详情页：统计 + 主题分布 + 合作机构 + 该机构论文列表
// 复用 PaperDetailView 模式：watch 路由参数重载；论文列表用局部状态（不污染全局筛选）
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getInstitutionDetail } from '../api/stats'
import { listPapers } from '../api/papers'
import TopicTag from '../components/TopicTag.vue'
import type { InstitutionDetail, PaperListItem } from '../types'

const route = useRoute()
const router = useRouter()

const detail = ref<InstitutionDetail | null>(null)
const loading = ref(true)

const papers = ref<PaperListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20

async function loadPapers(name: string) {
  try {
    const res = await listPapers({
      institution: name,
      page: page.value,
      page_size: pageSize,
      sort: 'newest',
    })
    papers.value = res.items
    total.value = res.total
  } catch (e) {
    console.error('机构论文列表加载失败', e)
  }
}

async function load() {
  loading.value = true
  try {
    const name = String(route.params.name)
    detail.value = await getInstitutionDetail(name)
    page.value = 1
    await loadPapers(name)
  } catch (e) {
    console.error('机构详情加载失败', e)
    detail.value = null
  } finally {
    loading.value = false
  }
}

watch(() => route.params.name, load, { immediate: true })

// 机构 → 机构详情（合作机构点击）
function goInstitution(name: string) {
  router.push({ name: 'institution-detail', params: { name } })
}

function goPaper(id: number) {
  router.push(`/papers/${id}`)
}

// 在完整列表页按机构筛选查看（复用 PaperListView 的 ?institution= 处理）
function openFullList() {
  if (!detail.value) return
  router.push({ path: '/', query: { institution: detail.value.name } })
}
</script>

<template>
  <div v-loading="loading" class="inst">
    <el-page-header class="back" @back="router.back()">
      <template #content>机构详情</template>
    </el-page-header>

    <el-empty v-if="!detail" description="机构不存在或无数据">
      <el-button type="primary" @click="router.push('/trend')">返回分析页</el-button>
    </el-empty>

    <template v-else>
      <!-- 头部统计 -->
      <el-card class="card" shadow="never">
        <div class="head">
          <h1 class="name">{{ detail.name }}</h1>
          <div class="stats">
            <div class="stat">
              <span class="num">{{ detail.paper_count }}</span>
              <span class="label">论文数</span>
            </div>
            <div class="stat">
              <span class="num">{{ detail.ai4se_count }}</span>
              <span class="label">AI4SE 论文</span>
            </div>
          </div>
          <el-button size="small" class="full-btn" @click="openFullList">在列表页查看全部</el-button>
        </div>
      </el-card>

      <!-- 主题分布 -->
      <el-card v-if="detail.topics.length" class="card" shadow="never">
        <template #header>
          <span class="card-title">研究主题分布</span>
        </template>
        <div class="topics">
          <span v-for="t in detail.topics" :key="t.slug" class="topic-item">
            <TopicTag :topic="t" />
            <span class="topic-count">{{ t.count }} 篇</span>
          </span>
        </div>
      </el-card>

      <!-- 合作机构 -->
      <el-card v-if="detail.co_institutions.length" class="card" shadow="never">
        <template #header>
          <span class="card-title">合作机构</span>
        </template>
        <div class="co-list">
          <el-link
            v-for="c in detail.co_institutions"
            :key="c.name"
            type="primary"
            class="co-link"
            @click="goInstitution(c.name)"
          >
            {{ c.name }} <span class="co-count">（{{ c.count }} 篇共同论文）</span>
          </el-link>
        </div>
      </el-card>

      <!-- 论文列表 -->
      <el-card class="card" shadow="never">
        <template #header>
          <span class="card-title">论文（{{ total }} 篇）</span>
        </template>
        <el-table :data="papers" stripe>
          <el-table-column label="标题" min-width="320">
            <template #default="{ row }">
              <el-link type="primary" @click="goPaper(row.id)">{{ row.title }}</el-link>
            </template>
          </el-table-column>
          <el-table-column prop="year" label="年份" width="80" align="center" />
          <el-table-column label="会议" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.venue" size="small" type="warning">{{ row.venue.short_name }}</el-tag>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="AI4SE" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.is_ai4se_confirmed" size="small" type="success">AI4SE</el-tag>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
        </el-table>
        <div class="pager">
          <el-pagination
            background
            layout="prev, pager, next, total"
            :total="total"
            :page-size="pageSize"
            :current-page="page"
            @current-change="(p: number) => { page = p; loadPapers(detail!.name) }"
          />
        </div>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.inst {
  max-width: 980px;
  margin: 0 auto;
  padding: 8px 24px 32px;
}
.back {
  margin-bottom: 16px;
}
.card {
  margin-bottom: 16px;
}
.card-title {
  font-weight: 600;
}
.head {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}
.name {
  font-size: 20px;
  margin: 0;
  flex: 1 1 300px;
  word-break: break-all;
}
.stats {
  display: flex;
  gap: 24px;
}
.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.num {
  font-size: 26px;
  font-weight: 700;
  color: var(--brand-primary);
}
.label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.full-btn {
  margin-left: auto;
}
.topics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
}
.topic-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.topic-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.co-list {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
.co-link {
  font-size: 14px;
}
.co-count {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.pager {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
.muted {
  color: var(--el-text-color-secondary);
}
</style>
