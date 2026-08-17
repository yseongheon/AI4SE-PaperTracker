<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import type { AggregateMode, TrendResponse } from '../types'
import { aggregateSeries } from '../utils/trends'

// 按需注册 ECharts 模块（体积最小化）
use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

const props = defineProps<{
  groupBy: 'topic' | 'venue' | 'year'
  data: TrendResponse | null
  aggregate: AggregateMode
}>()

// 年份分组（labels 是年份）无日/周粒度可言，恒按原样展示
const aggregated = computed(() => {
  if (!props.data) return { labels: [], series: [] }
  const mode: AggregateMode = props.groupBy === 'year' ? 'day' : props.aggregate
  return aggregateSeries(props.data.labels, props.data.series, mode)
})

const option = computed(() => ({
  tooltip: { trigger: 'axis' as const },
  legend: { type: 'scroll' as const, bottom: 0 },
  grid: { left: 50, right: 24, top: 30, bottom: 48 },
  xAxis: { type: 'category' as const, data: aggregated.value.labels, boundaryGap: false },
  yAxis: { type: 'value' as const, minInterval: 1 },
  series: aggregated.value.series.map((s) => ({
    name: s.name,
    type: 'line' as const,
    data: s.values,
    smooth: true,
    symbol: 'none',
    emphasis: { focus: 'series' as const },
  })),
}))

const loading = computed(() => !props.data)
</script>

<template>
  <div class="trend-chart">
    <v-chart v-if="!loading" :option="option" autoresize class="chart" />
    <el-skeleton v-else :rows="8" animated />
  </div>
</template>

<style scoped>
.trend-chart {
  width: 100%;
}
.chart {
  height: 420px;
}
</style>
