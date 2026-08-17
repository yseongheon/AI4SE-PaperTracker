<script setup lang="ts">
// M4 详情页：中文摘要 / 主题标签 / arXiv+DBLP/DOI 双链接 / 作者 / 英文摘要
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getPaper } from '../api/papers'
import TopicTag from '../components/TopicTag.vue'
import type { PaperDetail } from '../types'

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

      <div class="topics">
        <TopicTag v-for="t in paper.topics" :key="t.slug" :topic="t" />
      </div>

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
.card {
  margin-bottom: 16px;
}
.card-title {
  font-weight: 600;
}
.summary-zh {
  border-left: 4px solid #409eff;
}
.summary-zh p {
  font-size: 15px;
  line-height: 1.8;
}
.abstract {
  line-height: 1.7;
  color: #606266;
  white-space: pre-wrap;
}
.links {
  display: flex;
  gap: 24px;
}
.authors {
  color: #606266;
}
.muted {
  color: #909399;
}
</style>
