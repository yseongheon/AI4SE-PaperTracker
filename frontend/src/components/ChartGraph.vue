<script setup lang="ts">
// M7 作者合作网络图：节点大小=论文数、边粗细=共著论文数、力导向布局
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import type { CoauthorGraph } from '../types'

use([CanvasRenderer, GraphChart, TooltipComponent])

const props = defineProps<{ graph: CoauthorGraph }>()

const option = computed(() => {
  const maxPapers = Math.max(...props.graph.nodes.map((n) => n.paper_count), 1)
  const maxWeight = Math.max(...props.graph.links.map((l) => l.weight), 1)
  return {
    textStyle: { fontFamily: 'Poppins, Microsoft YaHei, sans-serif' },
    tooltip: {
      formatter: (p: { dataType: string; name: string; value: number; weight?: number }) =>
        p.dataType === 'node'
          ? `${p.name}<br/>论文 ${p.value} 篇`
          : `共著 ${p.weight} 篇`,
    },
    series: [
      {
        type: 'graph' as const,
        layout: 'force' as const,
        roam: true,
        draggable: true,
        force: { repulsion: 120, edgeLength: [40, 90], gravity: 0.12 },
        label: { show: true, fontSize: 10, formatter: '{b}' },
        data: props.graph.nodes.map((n) => ({
          id: n.id,
          name: n.name,
          value: n.paper_count,
          symbolSize: 10 + (n.paper_count / maxPapers) * 26,
          itemStyle: { color: '#fece14', borderColor: '#111827', borderWidth: 1 },
        })),
        links: props.graph.links.map((l) => ({
          source: l.source,
          target: l.target,
          weight: l.weight,
          lineStyle: { width: 1 + (l.weight / maxWeight) * 4, opacity: 0.5 },
        })),
        emphasis: { focus: 'adjacency' as const, lineStyle: { width: 3 } },
      },
    ],
  }
})
</script>

<template>
  <div class="chart-graph">
    <VChart class="chart" :option="option" />
  </div>
</template>

<style scoped>
.chart-graph {
  width: 100%;
}
.chart {
  height: 520px;
}
</style>
