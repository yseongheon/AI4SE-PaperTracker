<script setup lang="ts">
// M9 个人画像页（需登录）：标记统计 + 收藏主题分布 + 最近收藏
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getProfile } from '../api/users'
import TopicTag from '../components/TopicTag.vue'
import type { ProfileStats } from '../types'

const router = useRouter()
const profile = ref<ProfileStats | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    profile.value = await getProfile()
  } catch (e) {
    console.error('画像加载失败', e)
    ElMessage.error('画像加载失败')
  } finally {
    loading.value = false
  }
})

function goPaper(id: number) {
  router.push(`/papers/${id}`)
}
</script>

<template>
  <div v-loading="loading" class="profile-page">
    <template v-if="profile">
      <h2 class="page-title">{{ profile.username }} 的阅读画像</h2>

      <!-- 统计卡片 -->
      <div class="stats">
        <div class="stat-card">
          <div class="stat-num mono">{{ profile.counts.bookmark }}</div>
          <div class="stat-label">⭐ 收藏</div>
        </div>
        <div class="stat-card">
          <div class="stat-num mono">{{ profile.counts.read }}</div>
          <div class="stat-label">✓ 已读</div>
        </div>
        <div class="stat-card">
          <div class="stat-num mono">{{ profile.counts.read_later }}</div>
          <div class="stat-label">📌 稍后读</div>
        </div>
      </div>

      <!-- 收藏主题分布 -->
      <el-card class="card" shadow="never">
        <template #header>
          <span class="card-title">收藏论文主题分布</span>
        </template>
        <div v-if="profile.topic_dist.length" class="topic-bars">
          <div v-for="t in profile.topic_dist" :key="t.slug" class="topic-bar">
            <span class="topic-name">{{ t.name_zh }}</span>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{ width: `${(t.count / profile.topic_dist[0].count) * 100}%` }"
              />
            </div>
            <span class="topic-count mono">{{ t.count }}</span>
          </div>
        </div>
        <p v-else class="empty">还没有收藏论文——在列表页点 ⭐ 即可收藏</p>
      </el-card>

      <!-- 最近收藏 -->
      <el-card class="card" shadow="never">
        <template #header>
          <span class="card-title">最近收藏</span>
        </template>
        <ul v-if="profile.recent.length" class="recent">
          <li v-for="p in profile.recent" :key="p.id">
            <el-link type="primary" @click="goPaper(p.id)">{{ p.title }}</el-link>
            <span v-if="p.venue" class="muted">· {{ p.venue.short_name }} {{ p.year ?? '' }}</span>
            <span class="topics-inline">
              <TopicTag v-for="t in p.topics" :key="t.slug" :topic="t" />
            </span>
          </li>
        </ul>
        <p v-else class="empty">暂无收藏</p>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.profile-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 8px 24px 32px;
}
.page-title {
  font-size: 20px;
  margin-bottom: 16px;
}
.stats {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}
.stat-card {
  flex: 1;
  background: var(--brand-surface);
  border: 1px solid var(--brand-border);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
}
.stat-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--brand-text);
}
.stat-label {
  margin-top: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.card {
  margin-bottom: 16px;
}
.card-title {
  font-weight: 600;
}
.topic-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.topic-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.topic-name {
  width: 120px;
  font-size: 13px;
  color: var(--brand-text);
}
.bar-track {
  flex: 1;
  height: 10px;
  background: var(--el-fill-color-light);
  border-radius: 5px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: var(--brand-primary);
  border-radius: 5px;
  transition: width 0.3s;
}
.topic-count {
  width: 40px;
  text-align: right;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.recent {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.recent li {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.topics-inline {
  margin-left: auto;
  display: flex;
  gap: 4px;
}
.empty {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}
.muted {
  color: var(--el-text-color-secondary);
}
</style>
