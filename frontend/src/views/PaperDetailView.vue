<script setup lang="ts">
// M4 详情页：中文摘要 / 主题标签 / arXiv+DBLP/DOI 双链接 / 作者 / 英文摘要
// M6：亮点速读卡片 / 收藏·已读·稍后读标记 / 相关论文推荐
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getPaper, setMark } from '../api/papers'
import TopicTag from '../components/TopicTag.vue'
import type { MarkType, PaperDetail } from '../types'

const route = useRoute()
const router = useRouter()

const paper = ref<PaperDetail | null>(null)
const loading = ref(true)
const notFound = ref(false)

onMounted(async () => {
  try {
    paper.value = await getPaper(Number(route.params.id))
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status
    notFound.value = status === 404
    console.error('详情加载失败', e)
  } finally {
    loading.value = false
  }
})

// M6 标记 toggle：成功后局部更新，不整页刷新
async function toggleMark(type: MarkType) {
  if (!paper.value) return
  const next = !paper.value.marks[type]
  try {
    paper.value.marks = await setMark(paper.value.id, type, next)
  } catch (e) {
    console.error('标记失败', e)
  }
}

function goRelated(id: number) {
  router.push(`/papers/${id}`)
}

const MATCH_TEXT: Record<string, string> = {
  matched: '已匹配 A 会',
  pending: '待复核',
  none: '未匹配',
}

const STATUS_TEXT: Record<string, string> = {
  fetched: '已抓取',
  matched: '已匹配',
  classified: '已分类',
  ready: '就绪',
}
</script>

<template>
  <div v-loading="loading" class="detail">
    <el-page-header class="back" @back="router.back()">
      <template #content>论文详情</template>
    </el-page-header>

    <el-empty v-if="notFound" description="论文不存在（可能已删除）">
      <el-button type="primary" @click="router.push('/')">返回列表</el-button>
    </el-empty>

    <template v-if="paper">
      <h1 class="title">{{ paper.title }}</h1>

      <div class="meta">
        <el-tag v-if="paper.venue" type="warning">{{ paper.venue.short_name }}</el-tag>
        <el-tag v-if="paper.year" type="info">{{ paper.year }}</el-tag>
        <span v-if="paper.published_at" class="muted">发布于 {{ paper.published_at }}</span>
        <span class="muted">· {{ STATUS_TEXT[paper.status] ?? paper.status }}</span>
        <span v-if="paper.venue" class="muted">· {{ MATCH_TEXT[paper.match_status] ?? paper.match_status }}</span>
      </div>

      <!-- M6 阅读标记：收藏 / 已读 / 稍后读 -->
      <div class="mark-bar">
        <el-button
          size="small"
          round
          :type="paper.marks.bookmark ? 'primary' : 'default'"
          @click="toggleMark('bookmark')"
        >
          {{ paper.marks.bookmark ? '⭐ 已收藏' : '☆ 收藏' }}
        </el-button>
        <el-button
          size="small"
          round
          :type="paper.marks.read ? 'primary' : 'default'"
          @click="toggleMark('read')"
        >
          {{ paper.marks.read ? '✓ 已读' : '标记已读' }}
        </el-button>
        <el-button
          size="small"
          round
          :type="paper.marks.read_later ? 'primary' : 'default'"
          @click="toggleMark('read_later')"
        >
          {{ paper.marks.read_later ? '📌 稍后读' : '稍后读' }}
        </el-button>
      </div>

      <div class="topics">
        <TopicTag v-for="t in paper.topics" :key="t.slug" :topic="t" />
      </div>

      <!-- M6 亮点速读（LLM 生成，历史数据可回填） -->
      <el-card v-if="paper.highlights" class="card highlights" shadow="never">
        <template #header>
          <span class="card-title">亮点速读（LLM 生成）</span>
        </template>
        <div class="hl-row">
          <span class="hl-label">贡献</span>
          <span class="hl-text">{{ paper.highlights.contribution || '—' }}</span>
        </div>
        <div class="hl-row">
          <span class="hl-label hl-limit">局限</span>
          <span class="hl-text">{{ paper.highlights.limitation || '—' }}</span>
        </div>
      </el-card>

      <el-card v-if="paper.summary_zh" class="card summary-zh" shadow="never">
        <template #header>
          <span class="card-title">中文摘要（LLM 生成）</span>
        </template>
        <p>{{ paper.summary_zh }}</p>
      </el-card>

      <el-card v-if="paper.abstract" class="card" shadow="never">
        <template #header>
          <span class="card-title">英文摘要</span>
        </template>
        <p class="abstract">{{ paper.abstract }}</p>
      </el-card>

      <el-card class="card" shadow="never">
        <template #header>
          <span class="card-title">链接</span>
        </template>
        <div class="links">
          <el-link v-if="paper.arxiv_url" :href="paper.arxiv_url" target="_blank" type="primary">
            arXiv 预印本 ↗
          </el-link>
          <el-link v-if="paper.dblp_url" :href="paper.dblp_url" target="_blank" type="primary">
            DBLP 收录页 ↗
          </el-link>
          <el-link v-if="paper.doi" :href="`https://doi.org/${paper.doi}`" target="_blank" type="primary">
            DOI ↗
          </el-link>
          <span v-if="!paper.arxiv_url && !paper.dblp_url && !paper.doi" class="muted">暂无链接</span>
        </div>
      </el-card>

      <el-card v-if="paper.authors.length" class="card" shadow="never">
        <template #header>
          <span class="card-title">作者</span>
        </template>
        <p class="authors">{{ paper.authors.join('、') }}</p>
      </el-card>

      <!-- M6 相关论文推荐：同主题 + 标题相似 -->
      <el-card v-if="paper.related.length" class="card" shadow="never">
        <template #header>
          <span class="card-title">相关论文推荐</span>
        </template>
        <ul class="related">
          <li v-for="r in paper.related" :key="r.id">
            <el-link type="primary" @click="goRelated(r.id)">{{ r.title }}</el-link>
            <span v-if="r.venue" class="muted">· {{ r.venue.short_name }} {{ r.year ?? '' }}</span>
            <span v-if="r.marks.bookmark" class="muted">⭐</span>
          </li>
        </ul>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.detail {
  max-width: 900px;
  margin: 0 auto;
  padding: 8px 24px 32px;
}
.back {
  margin-bottom: 16px;
}
.title {
  font-size: 22px;
  line-height: 1.4;
  margin-bottom: 12px;
}
.meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.topics {
  margin-bottom: 16px;
}
.mark-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.card {
  margin-bottom: 16px;
}
.card-title {
  font-weight: 600;
}
.highlights {
  border-left: 4px solid var(--brand-primary);
}
.hl-row {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
  line-height: 1.7;
}
.hl-label {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  color: #111827;
  background: var(--brand-primary);
  border-radius: 4px;
  padding: 1px 8px;
  height: fit-content;
  margin-top: 3px;
}
.hl-limit {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
}
.hl-text {
  color: var(--brand-text);
}
.related {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.related .muted {
  margin-left: 4px;
}
.summary-zh {
  border-left: 4px solid var(--brand-primary);
}
.summary-zh p {
  font-size: 15px;
  line-height: 1.8;
  color: var(--brand-text);
}
.abstract {
  line-height: 1.7;
  color: var(--brand-text);
  white-space: pre-wrap;
}
.links {
  display: flex;
  gap: 24px;
}
.authors {
  color: var(--el-text-color-regular);
}
.muted {
  color: var(--el-text-color-secondary);
}
</style>
