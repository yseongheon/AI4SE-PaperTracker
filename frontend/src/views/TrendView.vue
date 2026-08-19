<script setup lang="ts">
// M4+M7 趋势页：多页签（主题/会议/年份/饼图/堆叠/热力/合作网络/词云/作者榜）+ 聚合粒度切换
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getAuthorsTop, getCoauthor, getCross, getTrends, getWords,
} from '../api/stats'
import { listTopics } from '../api/topics'
import { listVenues } from '../api/venues'
import ChartGraph from '../components/ChartGraph.vue'
import ChartHeatmap from '../components/ChartHeatmap.vue'
import ChartPie from '../components/ChartPie.vue'
import ChartWordcloud from '../components/ChartWordcloud.vue'
import TrendChart from '../components/TrendChart.vue'
import type {
  AggregateMode, AuthorStat, CoauthorGraph, CrossMatrix, TopicWithCount,
  TrendResponse, VenueWithCount, WordItem,
} from '../types'

const router = useRouter()
const activeTab = ref('topic')
const aggregate = ref<AggregateMode>('day')

const topicData = ref<TrendResponse | null>(null)
const venueData = ref<TrendResponse | null>(null)
const yearData = ref<TrendResponse | null>(null)
const topics = ref<TopicWithCount[]>([])
const venues = ref<VenueWithCount[]>([])
const cross = ref<CrossMatrix | null>(null)
const graph = ref<CoauthorGraph | null>(null)
const words = ref<WordItem[]>([])
const authors = ref<AuthorStat[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const [t, v, y, tops, vens, c, g, w, a] = await Promise.all([
      getTrends('topic'),
      getTrends('venue'),
      getTrends('year'),
      listTopics(),
      listVenues(),
      getCross(),
      getCoauthor(100),
      getWords(60),
      getAuthorsTop(30),
    ])
    topicData.value = t
    venueData.value = v
    yearData.value = y
    topics.value = tops
    venues.value = vens
    cross.value = c
    graph.value = g
    words.value = w
    authors.value = a
  } catch (e) {
    console.error('分析数据加载失败', e)
  } finally {
    loading.value = false
  }
})

// 饼图数据：主题/会议占比（按计数降序，取前 12 防图例拥挤）
const topicPie = computed(() =>
  topics.value.slice(0, 12).map((t) => ({ name: t.name_zh, value: t.paper_count })))
const venuePie = computed(() =>
  venues.value.map((v) => ({ name: v.short_name, value: v.paper_count })))

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
      <el-tab-pane label="占比分布" name="pie">
        <div class="pie-row">
          <div class="pie-col">
            <h3 class="pie-title">主题占比（Top 12）</h3>
            <ChartPie title="主题占比" :data="topicPie" />
          </div>
          <div class="pie-col">
            <h3 class="pie-title">会议占比</h3>
            <ChartPie title="会议占比" :data="venuePie" />
          </div>
        </div>
      </el-tab-pane>
      <el-tab-pane label="主题堆叠" name="stacked">
        <TrendChart group-by="topic" :data="topicData" :aggregate="aggregate" stacked />
      </el-tab-pane>
      <el-tab-pane label="会议×主题热力" name="heatmap">
        <ChartHeatmap
          v-if="cross"
          :venues="cross.venues"
          :topics="cross.topics"
          :matrix="cross.matrix"
        />
      </el-tab-pane>
      <el-tab-pane label="合作网络" name="graph">
        <ChartGraph v-if="graph" :graph="graph" />
        <p class="hint">TOP 100 活跃学者共著关系：节点大小=论文数、连线粗细=共著篇数，可拖拽缩放</p>
      </el-tab-pane>
      <el-tab-pane label="词云" name="wordcloud">
        <ChartWordcloud v-if="words.length" :words="words" />
        <p class="hint">AI4SE 论文摘要高频术语（停用词已过滤）</p>
      </el-tab-pane>
      <el-tab-pane label="作者榜" name="authors">
        <el-table :data="authors" stripe>
          <el-table-column type="index" label="#" width="56" align="center" />
          <el-table-column label="学者" min-width="200">
            <template #default="{ row }">
              <el-link type="primary" @click="goAuthor(row.name)">{{ row.name }}</el-link>
            </template>
          </el-table-column>
          <el-table-column prop="paper_count" label="论文数" width="90" align="center" />
          <el-table-column prop="ai4se_count" label="AI4SE 论文" width="110" align="center" />
          <el-table-column label="主要主题" min-width="260">
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
.pie-row {
  display: flex;
  gap: 24px;
}
.pie-col {
  flex: 1;
  min-width: 0;
}
.pie-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--brand-text);
}
.topic-tag {
  margin: 2px 4px 2px 0;
}
</style>
