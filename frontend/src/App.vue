<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getHealth } from './api/health'

const route = useRoute()
const backendOk = ref<boolean | null>(null)

onMounted(async () => {
  try {
    await getHealth()
    backendOk.value = true
  } catch {
    backendOk.value = false
  }
})
</script>

<template>
  <el-container class="layout">
    <el-aside width="208px" class="aside">
      <div class="logo">
        <span class="logo-mark">AI4SE</span>
        <span class="logo-sub">PaperTracker</span>
      </div>
      <el-menu router :default-active="route.path" class="menu">
        <el-menu-item index="/">论文列表</el-menu-item>
        <el-menu-item index="/trend">主题趋势</el-menu-item>
      </el-menu>
      <div class="aside-foot">CCF-A SE Venues<br />ICSE · FSE · ASE · ISSTA</div>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="title">{{ route.meta.title }}</span>
        <el-tag v-if="backendOk === true" type="success" size="small" round>后端已联通</el-tag>
        <el-tag v-else-if="backendOk === false" type="danger" size="small" round>后端未启动（8000 端口）</el-tag>
        <el-tag v-else type="info" size="small" round>检测中…</el-tag>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}

/* ---- 黑色侧栏 + 黄色高亮（Professional 黄黑品牌） ---- */
.aside {
  display: flex;
  flex-direction: column;
  background: #000;
  color: #fff;
}
.logo {
  padding: 20px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
}
.logo-mark {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 18px;
  color: var(--brand-primary);
  letter-spacing: 0.04em;
}
.logo-sub {
  font-size: 12px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.72);
  letter-spacing: 0.18em;
  text-transform: uppercase;
}
.menu {
  flex: 1;
  background: transparent;
  border-right: none;
  padding-top: 8px;
  --el-menu-text-color: rgba(255, 255, 255, 0.82);
  --el-menu-hover-bg-color: var(--brand-primary);
  --el-menu-hover-text-color: #111827;
  --el-menu-active-color: #111827;
  --el-menu-item-height: 46px;
}
.menu :deep(.el-menu-item) {
  margin: 2px 10px;
  border-radius: 6px;
  font-weight: 500;
  letter-spacing: 0.02em;
}
.menu :deep(.el-menu-item:hover) {
  background: var(--brand-primary);
  color: #111827;
}
.menu :deep(.el-menu-item.is-active) {
  background: var(--brand-primary);
  color: #111827;
  font-weight: 700;
}
.aside-foot {
  padding: 14px 16px;
  font-size: 11px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.42);
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  letter-spacing: 0.03em;
}

/* ---- 页头 ---- */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid var(--brand-border);
  box-shadow: 0 1px 2px rgba(17, 24, 39, 0.04);
}
.title {
  font-size: 16px;
  font-weight: 700;
  color: var(--brand-text);
}

.main {
  background: var(--el-bg-color-page);
  padding: var(--space-5);
}
</style>
