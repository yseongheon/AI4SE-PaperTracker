<script setup lang="ts">
// M7 摘要高频术语词云：字体大小=词频（ECharts wordCloud 插件）
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { TooltipComponent } from 'echarts/components'
import 'echarts-wordcloud' // 副作用注册 wordCloud 系列（echarts 6 兼容 extendSeriesModel）
import type { WordItem } from '../types'

use([CanvasRenderer, TooltipComponent])

const props = defineProps<{ words: WordItem[] }>()

const option = computed(() => {
  const maxCount = Math.max(...props.words.map((w) => w.count), 1)
  return {
    textStyle: { fontFamily: 'Poppins, Microsoft YaHei, sans-serif' },
    tooltip: {
      formatter: (p: { name: string; value: number }) => `${p.name}：${p.value} 次`,
    },
    series: [
      {
        type: 'wordCloud' as const,
        shape: 'circle',
        left: 'center',
        top: 'center',
        width: '92%',
        height: '90%',
        sizeRange: [12, 56],
        rotationRange: [0, 0], // 全部水平，便于阅读
        gridSize: 6,
        drawOutOfBound: false,
        textStyle: {
          fontFamily: 'Poppins, Microsoft YaHei, sans-serif',
          fontWeight: 600,
          color: () => {
            const palette = ['#111827', '#d4af0a', '#6b7280', '#9ca3af', '#374151']
            return palette[Math.floor(Math.random() * palette.length)]
          },
        },
        emphasis: { textStyle: { color: '#fece14', textShadowBlur: 6 } },
        data: props.words.map((w) => ({
          name: w.word,
          value: Math.max(1, Math.round((w.count / maxCount) * 100)),
        })),
      },
    ],
  }
})
</script>

<template>
  <div class="chart-wordcloud">
    <VChart class="chart" :option="option" />
  </div>
</template>

<style scoped>
.chart-wordcloud {
  width: 100%;
}
.chart {
  height: 420px;
}
</style>
