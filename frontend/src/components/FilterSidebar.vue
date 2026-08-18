<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useFilterStore } from '../stores/filterStore'
import type { TopicWithCount, VenueWithCount } from '../types'

// 筛选条件来自 /api/topics、/api/venues、趋势接口年份分组（数据驱动，不硬编码）
defineProps<{ topics: TopicWithCount[]; venues: VenueWithCount[]; years: number[] }>()

const filter = useFilterStore()
const { topic, venue, year, isAi4se, sort } = storeToRefs(filter)
</script>

<template>
  <aside class="sidebar">
    <div class="block">
      <div class="block-title">筛选</div>
      <el-button size="small" text type="primary" @click="filter.reset()">重置筛选</el-button>
    </div>
    <div class="block">
      <div class="block-title">AI4SE</div>
      <el-switch v-model="isAi4se" active-text="仅已确认 AI4SE" />
    </div>
    <div class="block">
      <div class="block-title">主题</div>
      <el-radio-group v-model="topic" class="vert">
        <el-radio value="">全部</el-radio>
        <el-radio v-for="t in topics" :key="t.slug" :value="t.slug">
          {{ t.name_zh }} ({{ t.paper_count }})
        </el-radio>
      </el-radio-group>
    </div>
    <div class="block">
      <div class="block-title">会议</div>
      <el-radio-group v-model="venue" class="vert">
        <el-radio value="">全部</el-radio>
        <el-radio v-for="v in venues" :key="v.short_name" :value="v.short_name">
          {{ v.short_name }} ({{ v.paper_count }})
        </el-radio>
      </el-radio-group>
    </div>
    <div class="block">
      <div class="block-title">年份</div>
      <el-radio-group v-model="year" class="vert">
        <el-radio :value="null">全部</el-radio>
        <el-radio v-for="y in years" :key="y" :value="y">{{ y }}</el-radio>
      </el-radio-group>
    </div>
    <div class="block">
      <div class="block-title">排序</div>
      <el-radio-group v-model="sort" class="vert">
        <el-radio value="newest">最新发布</el-radio>
        <el-radio value="venue">A 会优先</el-radio>
      </el-radio-group>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 230px;
  flex-shrink: 0;
  padding: 16px;
  background: var(--brand-surface);
  border-right: 1px solid var(--brand-border);
  overflow-y: auto;
}
.block {
  margin-bottom: 22px;
}
.block-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--brand-text-muted);
  font-size: 13px;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.vert {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
</style>
