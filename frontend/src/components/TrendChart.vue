<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
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

// 柱状图柱宽自动适配分类带宽（上限 20px≈月粒度宽度）；分类多（按天/按周）时
// 图表按估算宽度撑开，超出容器部分左右滚动查看
const BAR_WIDTH = 20 // 柱宽上限（barMaxWidth）
const BAR_STEP = 28 // 每根柱横向占用（柱宽 + 间距，决定横向滚动宽度）
const chartWidth = computed(() =>
  isBar.value ? aggregated.value.labels.length * BAR_STEP + 80 : undefined,
)

// 容器是否实际溢出（子图表宽超过可视区）→ 显示滚动提示
const scrollRef = ref<HTMLElement | null>(null)
const overflows = ref(false)
let resizeObs: ResizeObserver | null = null

function checkOverflow() {
  const el = scrollRef.value
  overflows.value = Boolean(el && el.scrollWidth > el.clientWidth + 1)
}
watch(scrollRef, (el) => {
  resizeObs?.disconnect()
  resizeObs = null
  if (el) {
    resizeObs = new ResizeObserver(checkOverflow)
    resizeObs.observe(el) // observe 即触发一次初始检查
  }
})
onBeforeUnmount(() => resizeObs?.disconnect())
// 聚合粒度切换/数据到达 → 图表宽变化 → 重测溢出（容器自身尺寸不变，ResizeObserver 不会触发）
watch(chartWidth, async () => {
  await nextTick()
  checkOverflow()
})

const option = computed(() => ({
  textStyle: { fontFamily: 'Poppins, Microsoft YaHei, sans-serif' },
  tooltip: { trigger: 'axis' as const },
  legend: {
    // 柱状图：分类图例放在图表上方固定展示（不随横向滚动条移动），画布内隐藏；
    // 折线图（年份）仍用画布内图例
    show: !isBar.value,
    type: 'scroll' as const,
    bottom: 0,
    // 仅在用户点过图例时才传 selected；null（默认全显）时省略该键——
    // 传 selected: undefined 会在 ECharts mergeOption 时把 option.selected 覆盖为
    // undefined（init 有 || {} 兜底、merge 没有），导致 legendFilter 里
    // isSelected 读 undefined.hasOwnProperty 崩溃（点按周/按月即触发）。
    // selected 对系列显隐的控制不依赖 legend 是否显示，柱状图同样生效。
    ...(legendSelected.value ? { selected: legendSelected.value } : {}),
  },
  // 柱状图图例在画布外 → 底部省出图例空间
  grid: { left: 50, right: 24, top: 30, bottom: isBar.value ? 30 : 48 },
  // 柱状图留出柱宽边距，折线图贴边（时间序列）
  xAxis: { type: 'category' as const, data: aggregated.value.labels, boundaryGap: isBar.value },
  yAxis: { type: 'value' as const, minInterval: 1 },
  series: aggregated.value.series.map((s) => ({
    name: s.name,
    type: isBar.value ? ('bar' as const) : ('line' as const),
    data: s.values,
    barMaxWidth: isBar.value ? BAR_WIDTH : undefined,
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

// 柱状图分类图例（画布外固定标签）：当前显示的分类集合
const shownNames = computed(() => {
  const names = aggregated.value.series.map((s) => s.name)
  if (!legendSelected.value) return new Set(names)
  return new Set(names.filter((n) => legendSelected.value![n]))
})
function isSeriesOn(name: string) {
  return shownNames.value.has(name)
}
// 与画布内图例语义一致：单击=只看该分类；再击唯一选中项=恢复全部；其余=toggle
function toggleSeries(name: string) {
  const names = aggregated.value.series.map((s) => s.name)
  if (names.length <= 1) return
  const shown = shownNames.value
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

const loading = computed(() => !props.data)
</script>

<template>
  <div class="trend-chart">
    <div v-if="!loading && isBar" class="series-chips">
      <el-check-tag
        v-for="s in aggregated.series"
        :key="s.key"
        :checked="isSeriesOn(s.name)"
        class="series-chip"
        @change="toggleSeries(s.name)"
      >
        {{ s.name }}
      </el-check-tag>
    </div>
    <div v-if="!loading" ref="scrollRef" class="chart-scroll">
      <v-chart
        :option="option"
        autoresize
        class="chart"
        :style="chartWidth ? { width: `max(100%, ${chartWidth}px)` } : undefined"
        @legendselectchanged="onLegendSelectChanged"
      />
      <p v-if="overflows" class="scroll-hint">时间跨度较长，左右滚动查看完整走势</p>
    </div>
    <el-skeleton v-else :rows="8" animated />
  </div>
</template>

<style scoped>
.trend-chart {
  width: 100%;
}
.series-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.chart-scroll {
  overflow-x: auto;
}
.chart {
  height: 420px;
}
.scroll-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
