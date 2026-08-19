<script setup lang="ts">
// M7 会议×主题交叉热力图：行=会议、列=主题、颜色=论文数
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'

use([CanvasRenderer, HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent])

const props = defineProps<{
  venues: string[]
  topics: string[]
  matrix: number[][]
}>()

const option = computed(() => ({
  textStyle: { fontFamily: 'Poppins, Microsoft YaHei, sans-serif' },
  tooltip: {
    position: 'top' as const,
    formatter: (p: { value: number[] }) =>
      `${props.venues[p.value[1]]} × ${props.topics[p.value[0]]}：${p.value[2]} 篇`,
  },
  grid: { left: 90, right: 40, top: 30, bottom: 130 },
  xAxis: {
    type: 'category' as const,
    data: props.topics,
    axisLabel: {
      rotate: 30,
      fontFamily: 'Poppins, Microsoft YaHei, sans-serif',
      margin: 12,
    },
    splitArea: { show: true },
  },
  yAxis: {
    type: 'category' as const,
    data: props.venues,
    splitArea: { show: true },
  },
  visualMap: {
    min: 0,
    max: Math.max(...props.matrix.flat(), 1),
    calculable: true,
    orient: 'horizontal',
    left: 'center',
    bottom: 8,
    inRange: { color: ['#fffbea', '#fece14', '#d4af0a'] },
    textStyle: { fontFamily: 'Poppins, Microsoft YaHei, sans-serif' },
  },
  series: [
    {
      type: 'heatmap' as const,
      data: props.matrix.flatMap((row, y) => row.map((v, x) => [x, y, v])),
      label: { show: true, fontSize: 10 },
      emphasis: { itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.3)' } },
    },
  ],
}))
</script>

<template>
  <div class="chart-heatmap">
    <VChart class="chart" :option="option" autoresize />
  </div>
</template>

<style scoped>
.chart-heatmap {
  width: 100%;
}
.chart {
  height: 520px; /* M7 拍板：全宽大图 */
}
</style>
