<script setup lang="ts">
// M4 趋势页（DR-020）：多页签（主题/会议/年份）+ 聚合粒度切换（日/周/月，前端聚合）
import { onMounted, ref } from 'vue'
import { getTrends } from '../api/stats'
import TrendChart from '../components/TrendChart.vue'
import type { AggregateMode, TrendResponse } from '../types'

const activeTab = ref('topic')
const aggregate = ref<AggregateMode>('day')

const topicData = ref<TrendResponse | null>(null)
const venueData = ref<TrendResponse | null>(null)
const yearData = ref<TrendResponse | null>(null)

onMounted(async () => {
  try {
    const [t, v, y] = await Promise.all([
      getTrends('topic'),
      getTrends('venue'),
      getTrends('year'),
    ])
    topicData.value = t
    venueData.value = v
    yearData.value = y
  } catch (e) {
    console.error('趋势数据加载失败', e)
  }
})
</script>

<template>
  <div class="trend-page">
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
      </el-tab-pane>
      <el-tab-pane label="会议趋势" name="venue">
        <TrendChart group-by="venue" :data="venueData" :aggregate="aggregate" />
      </el-tab-pane>
      <el-tab-pane label="年份分布" name="year">
        <TrendChart group-by="year" :data="yearData" :aggregate="aggregate" />
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
  color: #909399;
  font-size: 13px;
}
</style>
