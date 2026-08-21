<script setup lang="ts">
// 会议×主题分组柱状图：x=会议，每个会议下各主题的柱并排对比（与「会议趋势」同风格：
// 画布上方为主题分类标签，单击只看该主题、再击恢复全部）
import { computed, ref } from 'vue'
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

// 每个主题一条分组系列（不堆叠）：data[v] = 第 v 个会议中该主题的论文数
const series = computed(() =>
  props.topics.map((topic, t) => ({
    name: topic,
    type: 'bar' as const,
    data: props.venues.map((_, v) => props.matrix[v]?.[t] ?? 0),
    emphasis: { focus: 'series' as const },
  })),
)

// 主题标签显隐状态：null=全部显示；否则为每主题是否显示（与会议趋势页签交互一致）
const legendSelected = ref<Record<string, boolean> | null>(null)

// ECharts 图例显隐的唯一事实来源：null（全部显示）时展开成全 true 映射——
// mergeOption 用 zrUtil.merge(target, src, true)，缺省键沿用旧值，
// 所以「恢复全部」必须显式传全 true 才能真的重置（柱状图同样生效）
const legendSelectedMap = computed(() => {
  const names = props.topics
  return legendSelected.value ?? Object.fromEntries(names.map((n) => [n, true]))
})

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
    show: false, // 画布内隐藏，用上方的分类标签筛选（与会议趋势一致）
    type: 'scroll' as const,
    top: 0,
    textStyle: { fontFamily: 'Poppins, Microsoft YaHei, sans-serif' },
    // 始终显式传完整 selected 映射，既不省略（恢复失效）也不传 undefined（崩溃）
    selected: legendSelectedMap.value,
  },
  grid: { left: 50, right: 24, top: 40, bottom: 30 },
  xAxis: { type: 'category' as const, data: props.venues },
  yAxis: { type: 'value' as const, minInterval: 1 },
  series: series.value,
}))

// 当前显示的主题集合
const shownTopics = computed(() => {
  if (!legendSelected.value) return new Set(props.topics)
  return new Set(props.topics.filter((n) => legendSelected.value![n]))
})

// 与会议趋势标签语义一致：单击=只看该主题；再击唯一选中项=恢复全部；其余=toggle
function toggleTopic(name: string) {
  const names = props.topics
  if (names.length <= 1) return
  const shown = shownTopics.value
  if (shown.size === names.length) {
    legendSelected.value = Object.fromEntries(names.map((n) => [n, n === name]))
  } else if (shown.size === 1 && shown.has(name)) {
    legendSelected.value = null
  } else {
    const next = Object.fromEntries(names.map((n) => [n, shown.has(n)]))
    next[name] = !next[name]
    legendSelected.value = names.every((n) => next[n]) ? null : next
  }
}
</script>

<template>
  <div class="chart-cross">
    <div class="series-chips">
      <el-check-tag
        v-for="s in topics"
        :key="s"
        :checked="shownTopics.has(s)"
        class="series-chip"
        @change="toggleTopic(s)"
      >
        {{ s }}
      </el-check-tag>
    </div>
    <VChart class="chart" :option="option" autoresize />
  </div>
</template>

<style scoped>
.chart-cross {
  width: 100%;
}
.series-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.chart {
  height: 420px;
}
</style>
