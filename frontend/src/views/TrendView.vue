<script setup lang="ts">
// M4+M7 趋势页：多页签（主题/会议/年份折线 + 热力 + 作者榜）+ 聚合粒度切换
// M7 拍板：精简分析图表（只留作者榜+热力），全宽大图
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAuthorsTop, getCross, getTrends } from '../api/stats'
import ChartHeatmap from '../components/ChartHeatmap.vue'
import TrendChart from '../components/TrendChart.vue'
import type {
  AggregateMode, AuthorStat, CrossMatrix, TrendResponse,
} from '../types'

const router = useRouter()
const activeTab = ref('topic')
const aggregate = ref<AggregateMode>('day')

const topicData = ref<TrendResponse | null>(null)
const venueData = ref<TrendResponse | null>(null)
const yearData = ref<TrendResponse | null>(null)
const cross = ref<CrossMatrix | null>(null)
const authors = ref<AuthorStat[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const [t, v, y, c, a] = await Promise.all([
      getTrends('topic'),
      getTrends('venue'),
      getTrends('year'),
      getCross(),
      getAuthorsTop(30),
    ])
    topicData.value = t
    venueData.value = v
    yearData.value = y
    cross.value = c
    authors.value = a
  } catch (e) {
    console.error('分析数据加载失败', e)
  } finally {
    loading.value = false
  }
})

// 作者榜 → 列表页按作者过滤
function goAuthor(name: string) {
  router.push({ path: '/', query: { author: name } })
}
</script>

<template>
  <div v-loading="loading" class="trend-page">
    <div class="toolbar">
      <span class="label">聚合粒度（后端按天返回，前端聚合）</span>
      <el-radio-group v-model="aggregate">
        <el-radio-button value="day">按天</el-radio-button>
        <el-radio-button value="week">按周</el-radio-button>
        <el-radio-button value="month">按月</el-radio-button>
      </el-radio-group>
    </div>
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="主题趋势" name="topic">
        <TrendChart group-by="topic" :data="topicData" :aggregate="aggregate" />
        <p class="hint">点击图例系列名：只看该主题；再次点击：恢复全部</p>
      </el-tab-pane>
      <el-tab-pane label="会议趋势" name="venue">
        <TrendChart group-by="venue" :data="venueData" :aggregate="aggregate" />
        <p class="hint">点击图例系列名：只看该会议；再次点击：恢复全部</p>
      </el-tab-pane>
      <el-tab-pane label="年份分布" name="year">
        <TrendChart group-by="year" :data="yearData" :aggregate="aggregate" />
      </el-tab-pane>
      <el-tab-pane label="会议×主题热力" name="heatmap">
        <ChartHeatmap
          v-if="cross"
          :venues="cross.venues"
          :topics="cross.topics"
          :matrix="cross.matrix"
        />
        <p class="hint">颜色越深论文越多：快速定位「哪个会议更关注哪个主题」</p>
      </el-tab-pane>
      <el-tab-pane label="作者榜" name="authors">
        <el-table :data="authors" stripe>
          <el-table-column type="index" label="#" width="56" align="center" />
          <el-table-column label="学者" min-width="220">
            <template #default="{ row }">
              <el-link type="primary" @click="goAuthor(row.name)">{{ row.name }}</el-link>
            </template>
          </el-table-column>
          <el-table-column prop="paper_count" label="论文数" width="100" align="center" />
          <el-table-column prop="ai4se_count" label="AI4SE 论文" width="120" align="center" />
          <el-table-column label="主要主题" min-width="300">
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
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.trend-page {
  padding: 16px 20px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.hint {
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.topic-tag {
  margin: 2px 4px 2px 0;
}
</style>
