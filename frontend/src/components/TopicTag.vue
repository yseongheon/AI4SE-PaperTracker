<script setup lang="ts">
import { computed } from 'vue'

// 只依赖 slug/name_zh：机构详情主题（无 id）也可复用（M12）
const props = defineProps<{ topic: { slug: string; name_zh: string } }>()

type TagType = '' | 'success' | 'warning' | 'info' | 'danger'
// 10 主题配色（与 topics 表 slug 对应）
const COLOR: Record<string, TagType> = {
  llm4se_general: '',
  code_generation: 'success',
  code_repair: 'danger',
  code_translation: 'warning',
  code_summarization: 'info',
  defect_detection: 'danger',
  testing: 'success',
  analysis: 'info',
  requirements: 'warning',
  other: 'info',
}

const type = computed(() => COLOR[props.topic.slug] ?? 'info')
</script>

<template>
  <el-tag :type="type" size="small" class="topic-tag">{{ topic.name_zh }}</el-tag>
</template>

<style scoped>
.topic-tag {
  margin: 2px 4px 2px 0;
}
</style>
