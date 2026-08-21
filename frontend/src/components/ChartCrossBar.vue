<script setup lang="ts">
// 会议×主题交叉堆叠柱状图：x=会议，柱内按主题分色堆叠（替代 M7 热力图）
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, GridComponent, LegendComponent, TooltipComponent])

const props = defineProps<{
  venues: string[]
  topics: string[]
  matrix: number[][]
}>()

// 每个主题一条堆叠系列：data[i] = 第 i 个会议中该主题的论文数
const series = computed(() =>
  props.topics.map((topic, t) => ({
    name: topic,
    type: 'bar' as const,
    stack: 'total',
    barWidth: 40, // 会议数少，固定较宽柱
    data: props.venues.map((_, v) => props.matrix[v]?.[t] ?? 0),
    emphasis: { focus: 'series' as const },
  })),
)

const option = computed(() => ({
  textStyle: { fontFamily: 'Poppins, Microsoft YaHei, sans-serif' },
  tooltip: {
    trigger: 'axis' as const,
    axisPointer: { type: 'shadow' as const },
    formatter: (params: unknown) => {
      const list = params as Array<{
        name: string
        marker: string
        seriesName: string
        value: number | string
      }>
      if (!list.length) return ''
      const total = list.reduce((s, p) => s + (Number(p.value) || 0), 0)
      const rows = list
        .map((p) => `${p.marker}${p.seriesName}：${p.value} 篇`)
        .join('<br/>')
      return `${list[0].name}<br/>${rows}<br/><b>合计：${total} 篇</b>`
    },
  },
  legend: {
    type: 'scroll' as const,
    top: 0,
    textStyle: { fontFamily: 'Poppins, Microsoft YaHei, sans-serif' },
  },
  grid: { left: 50, right: 24, top: 40, bottom: 30 },
  xAxis: { type: 'category' as const, data: props.venues },
  yAxis: { type: 'value' as const, minInterval: 1 },
  series: series.value,
}))
</script>

<template>
  <div class="chart-cross">
    <VChart class="chart" :option="option" autoresize />
  </div>
</template>

<style scoped>
.chart-cross {
  width: 100%;
}
.chart {
  height: 420px;
}
</style>
