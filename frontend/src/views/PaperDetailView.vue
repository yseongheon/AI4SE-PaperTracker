<script setup lang="ts">
// M4 详情页：中文摘要 / 主题标签 / arXiv+DBLP/DOI 双链接 / 作者 / 英文摘要
// M6：亮点速读卡片 / 收藏·已读·稍后读标记 / 相关论文推荐
// M7：AI 深度摘要（按需生成+缓存）/ BibTeX 一键复制 / PDF 直达 / 作者点击
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getBibtex, getDeepSummary, getPaper, setMark } from '../api/papers'
import TopicTag from '../components/TopicTag.vue'
import { useAuthStore } from '../stores/authStore'
import type { DeepSummary, MarkType, PaperDetail } from '../types'

const route = useRoute()
const router = useRouter()

const paper = ref<PaperDetail | null>(null)
const loading = ref(true)
const notFound = ref(false)

// 关键：详情 → 详情跳转时组件复用、onMounted 不重跑，必须监听路由参数变化重新加载
async function loadPaper() {
  loading.value = true
  notFound.value = false
  try {
    paper.value = await getPaper(Number(route.params.id))
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status
    notFound.value = status === 404
    console.error('详情加载失败', e)
  } finally {
    loading.value = false
  }
}

watch(() => route.params.id, loadPaper, { immediate: true })

// M6 标记 toggle：成功后局部更新，不整页刷新（M9 需登录）
async function toggleMark(type: MarkType) {
  if (!paper.value) return
  if (!requireLogin()) return
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

// M9 标记需登录：未登录点击 → 提示并跳登录页
function requireLogin(): boolean {
  if (useAuthStore().isLoggedIn) return true
  ElMessage.warning('请先登录后再使用收藏 / 已读 / 稍后读')
  router.push({ path: '/login', query: { redirect: route.fullPath } })
  return false
}

// M7 AI 深度摘要：按需生成（后端缓存复用）；生成中禁用按钮
const deepSummary = ref<DeepSummary | null>(null)
const deepLoading = ref(false)

async function loadDeepSummary() {
  if (!paper.value || deepLoading.value) return
  deepLoading.value = true
  try {
    deepSummary.value = await getDeepSummary(paper.value.id)
  } catch (e) {
    console.error('深度摘要生成失败', e)
    ElMessage.error('深度摘要生成失败，请稍后重试')
  } finally {
    deepLoading.value = false
  }
}

// M7 BibTeX 一键复制（科研引用刚需）
async function copyBibtex() {
  if (!paper.value) return
  try {
    const bib = await getBibtex(paper.value.id)
    await navigator.clipboard.writeText(bib)
    ElMessage.success('BibTeX 已复制到剪贴板')
  } catch (e) {
    console.error('BibTeX 复制失败', e)
    ElMessage.error('复制失败，请手动复制或下载')
  }
}

// M7 作者点击 → 列表页按作者过滤
function goAuthor(name: string) {
  router.push({ path: '/', query: { author: name } })
}

const DEEP_LABELS: Record<string, string> = {
  background: '背景',
  problem: '问题',
  method: '方法',
  results: '实验',
  conclusion: '结论',
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
        <el-tooltip
          v-if="paper.citation_count != null"
          :content="`被引 ${paper.citation_count} 次（Crossref / Semantic Scholar 双源统计）`"
          placement="top"
        >
          <el-tag type="warning" effect="plain" style="cursor: help">
            🔥 被引 {{ paper.citation_count }}
          </el-tag>
        </el-tooltip>
        <span v-if="paper.published_at" class="muted">发布于 {{ paper.published_at }}</span>
        <span class="muted">· {{ STATUS_TEXT[paper.status] ?? paper.status }}</span>
        <span v-if="paper.venue" class="muted">· {{ MATCH_TEXT[paper.match_status] ?? paper.match_status }}</span>
      </div>

      <!-- M6 阅读标记：收藏 / 已读 / 稍后读 -->
      <div class="mark-bar">
        <el-tooltip content="收藏：在「个人画像」里集中回顾与管理" placement="top">
          <el-button
            size="small"
            round
            :type="paper.marks.bookmark ? 'primary' : 'default'"
            @click="toggleMark('bookmark')"
          >
            {{ paper.marks.bookmark ? '⭐ 已收藏' : '☆ 收藏' }}
          </el-button>
        </el-tooltip>
        <el-tooltip content="已读：列表里该行会淡化显示，可用于「只看未读」筛选" placement="top">
          <el-button
            size="small"
            round
            :type="paper.marks.read ? 'primary' : 'default'"
            @click="toggleMark('read')"
          >
            {{ paper.marks.read ? '✓ 已读' : '标记已读' }}
          </el-button>
        </el-tooltip>
        <el-tooltip content="稍后读：待读清单，可在列表「阅读状态」里筛选" placement="top">
          <el-button
            size="small"
            round
            :type="paper.marks.read_later ? 'primary' : 'default'"
            @click="toggleMark('read_later')"
          >
            {{ paper.marks.read_later ? '📌 稍后读' : '稍后读' }}
          </el-button>
        </el-tooltip>
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

      <!-- M7 AI 深度摘要（按需生成+缓存）：背景/问题/方法/实验/结论 -->
      <el-card class="card" shadow="never">
        <template #header>
          <span class="card-title">AI 深度摘要</span>
          <el-button
            v-if="!deepSummary"
            size="small"
            type="primary"
            class="deep-btn"
            :loading="deepLoading"
            @click="loadDeepSummary"
          >
            {{ deepLoading ? '生成中…' : '生成深度摘要' }}
          </el-button>
          <el-button
            v-else
            size="small"
            text
            class="deep-btn"
            @click="deepSummary = null"
          >
            收起
          </el-button>
        </template>
        <template v-if="deepSummary">
          <div v-for="(text, key) in deepSummary" :key="key" class="hl-row">
            <span class="hl-label">{{ DEEP_LABELS[key] }}</span>
            <span class="hl-text">{{ text }}</span>
          </div>
          <p class="deep-hint">快速判断该论文与课题的相关性：背景 → 问题 → 方法 → 实验 → 结论</p>
        </template>
        <p v-else class="deep-empty">
          一键生成结构化摘要（研究背景 / 要解决的问题 / 方法 / 主要实验 / 结论），快速判断是否与课题相关
        </p>
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
            arXiv 摘要页 ↗
          </el-link>
          <el-link v-if="paper.pdf_url" :href="paper.pdf_url" target="_blank" type="primary">
            PDF 直达 ↗
          </el-link>
          <el-button
            v-if="paper.id"
            size="small"
            class="copy-bib"
            @click="copyBibtex"
          >
            复制 BibTeX
          </el-button>
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
          <span class="card-title">作者（点击查看该作者全部论文）</span>
        </template>
        <p class="authors">
          <el-link
            v-for="(a, i) in paper.authors"
            :key="i"
            type="primary"
            class="author-link"
            @click="goAuthor(a)"
          >
            {{ a }}<span v-if="i < paper.authors.length - 1">、</span>
          </el-link>
        </p>
      </el-card>

      <!-- M6 相关论文推荐：同主题 + 标题相似 -->
      <el-card v-if="paper.related.length" class="card" shadow="never">
        <template #header>
          <span class="card-title">相关论文推荐</span>
        </template>
        <ul class="related">
          <li
            v-for="r in paper.related"
            :key="r.id"
            class="related-item"
            @click="goRelated(r.id)"
          >
            <!-- 标题用 RouterLink 保证跳转可靠；整行点击也跳转（双保险） -->
            <RouterLink
              :to="`/papers/${r.id}`"
              class="related-link"
              :title="`查看《${r.title}》详情`"
            >
              {{ r.title }} <span class="related-arrow">→</span>
            </RouterLink>
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
  gap: 6px;
}
.related li {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  transition: background 0.15s;
}
.related li:hover {
  background: var(--brand-bg-soft);
  cursor: pointer;
}
.related-link {
  text-decoration-thickness: 1px;
  color: inherit;
}
.related-link:hover {
  background: transparent; /* 整行 hover 高亮已由 li 承担 */
}
.related-arrow {
  color: var(--brand-primary);
  font-weight: 700;
  transition: margin-left 0.15s;
}
.related li:hover .related-arrow {
  margin-left: 4px;
}
.related .muted {
  margin-left: 2px;
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
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}
.copy-bib {
  margin-left: auto;
}
.authors {
  color: var(--el-text-color-regular);
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.author-link {
  text-decoration-thickness: 1px;
  font-weight: 500;
}
.deep-btn {
  float: right;
  margin-top: -4px;
}
.deep-empty {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.7;
}
.deep-hint {
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
.muted {
  color: var(--el-text-color-secondary);
}
</style>
