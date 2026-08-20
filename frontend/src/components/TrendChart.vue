<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import type { AggregateMode, TrendResponse } from '../types'
import { aggregateSeries } from '../utils/trends'

// 按需注册 ECharts 模块（体积最小化）
use([CanvasRenderer, BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent])

const props = defineProps<{
  groupBy: 'topic' | 'venue' | 'year'
  data: TrendResponse | null
  aggregate: AggregateMode
  chartType?: 'line' | 'bar' // 柱状/折线，默认折线
  stacked?: boolean // M7 堆叠面积图
}>()

// M7 图例交互状态：null=全部显示；否则为每系列是否显示
const legendSelected = ref<Record<string, boolean> | null>(null)

// 年份分组（labels 是年份）无日/周粒度可言，恒按原样展示
const aggregated = computed(() => {
  if (!props.data) return { labels: [], series: [] }
  const mode: AggregateMode = props.groupBy === 'year' ? 'day' : props.aggregate
  return aggregateSeries(props.data.labels, props.data.series, mode)
})

const isBar = computed(() => props.chartType === 'bar')

const option = computed(() => ({
  textStyle: { fontFamily: 'Poppins, Microsoft YaHei, sans-serif' },
  tooltip: { trigger: 'axis' as const },
  legend: {
    type: 'scroll' as const,
    bottom: 0,
    selected: legendSelected.value ?? undefined,
  },
  grid: { left: 50, right: 24, top: 30, bottom: 48 },
  // 柱状图留出柱宽边距，折线图贴边（时间序列）
  xAxis: { type: 'category' as const, data: aggregated.value.labels, boundaryGap: isBar.value },
  yAxis: { type: 'value' as const, minInterval: 1 },
  series: aggregated.value.series.map((s) => ({
    name: s.name,
    type: isBar.value ? ('bar' as const) : ('line' as const),
    data: s.values,
    barMaxWidth: isBar.value ? 20 : undefined,
    smooth: isBar.value ? undefined : true,
    symbol: isBar.value ? undefined : 'none',
    stack: props.stacked ? 'total' : undefined,
    areaStyle: props.stacked && !isBar.value ? { opacity: 0.65 } : undefined,
    emphasis: { focus: 'series' as const },
  })),
}))

// 单击系列名=只看该系列；再击唯一选中项=恢复全部；全部点掉=恢复全部
function onLegendSelectChanged(params: unknown) {
  const { name, selected } = params as { name: string; selected: Record<string, boolean> }
  const seriesNames = aggregated.value.series.map((s) => s.name)
  if (seriesNames.length <= 1) return
  const selectedNames = Object.keys(selected).filter((n) => selected[n])

  if (selectedNames.length === 0) {
    legendSelected.value = null // 全部点掉 → 恢复全部
  } else if (selectedNames.length === seriesNames.length - 1 && !selected[name]) {
    // 点掉了原本选中的 X（其余全选）→ 只看 X
    legendSelected.value = Object.fromEntries(
      seriesNames.map((n) => [n, n === name]),
    )
  }
  // 其余情况（多系列叠加对比）：保持 ECharts 默认 toggle 行为
}

const loading = computed(() => !props.data)
</script>

<template>
  <div class="trend-chart">
    <v-chart
      v-if="!loading"
      :option="option"
      autoresize
      class="chart"
      @legendselectchanged="onLegendSelectChanged"
    />
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
