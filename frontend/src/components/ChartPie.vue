<script setup lang="ts">
// M7 占比饼图：主题占比 / 会议占比（数据驱动，hover 显示数量与百分比）
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { LegendComponent, TooltipComponent } from 'echarts/components'

use([CanvasRenderer, PieChart, LegendComponent, TooltipComponent])

const props = defineProps<{
  title: string
  data: { name: string; value: number }[]
}>()

const option = computed(() => ({
  textStyle: { fontFamily: 'Poppins, Microsoft YaHei, sans-serif' },
  tooltip: {
    trigger: 'item',
    formatter: (p: { name: string; value: number; percent: number }) =>
      `${p.name}：${p.value} 篇（${p.percent}%）`,
  },
  legend: { bottom: 0, type: 'scroll' as const },
  series: [
    {
      name: props.title,
      type: 'pie' as const,
      radius: ['38%', '64%'],
      center: ['50%', '44%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontWeight: 700 } },
      data: props.data,
    },
  ],
}))
</script>

<template>
  <div class="chart-pie">
    <VChart class="chart" :option="option" />
  </div>
</template>

<style scoped>
.chart-pie {
  width: 100%;
}
.chart {
  height: 420px;
}
</style>
