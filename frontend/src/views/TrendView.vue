<script setup lang="ts">
// M4+M7 趋势页：多页签（主题/会议 + 会议×主题堆叠）+ 聚合粒度切换；作者·机构榜已抽为独立页 LeaderboardView（M14）
import { onMounted, ref } from 'vue'
import { getCross, getTrends } from '../api/stats'
import ChartCrossBar from '../components/ChartCrossBar.vue'
import TrendChart from '../components/TrendChart.vue'
import type { AggregateMode, CrossMatrix, TrendResponse } from '../types'

const activeTab = ref('topic')
const aggregate = ref<AggregateMode>('day')

const topicData = ref<TrendResponse | null>(null)
const venueData = ref<TrendResponse | null>(null)
const cross = ref<CrossMatrix | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    const [t, v, c] = await Promise.all([
      getTrends('topic'),
      getTrends('venue'),
      getCross(),
    ])
    topicData.value = t
    venueData.value = v
    cross.value = c
  } catch (e) {
    console.error('分析数据加载失败', e)
  } finally {
    loading.value = false
  }
})

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
        <TrendChart group-by="topic" :data="topicData" :aggregate="aggregate" chart-type="bar" />
        <p class="hint">点击上方分类标签：只看该主题；再次点击：恢复全部</p>
      </el-tab-pane>
      <el-tab-pane label="会议趋势" name="venue">
        <TrendChart group-by="venue" :data="venueData" :aggregate="aggregate" chart-type="bar" />
        <p class="hint">点击上方分类标签：只看该会议；再次点击：恢复全部</p>
      </el-tab-pane>
      <el-tab-pane label="会议×主题分布" name="heatmap">
        <ChartCrossBar
          v-if="cross"
          :venues="cross.venues"
          :topics="cross.topics"
          :matrix="cross.matrix"
        />
        <p class="hint">每个会议一组柱、各主题并排对比：快速定位「哪个会议更关注哪个主题」；点击上方主题标签可单独对比</p>
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
</style>
