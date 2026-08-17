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
    <el-aside width="200px">
      <div class="logo">AI4SE PaperTracker</div>
      <el-menu router :default-active="route.path" class="menu">
        <el-menu-item index="/">论文列表</el-menu-item>
        <el-menu-item index="/trend">主题趋势</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="title">{{ route.meta.title }}</span>
        <el-tag v-if="backendOk === true" type="success" size="small">后端已联通</el-tag>
        <el-tag v-else-if="backendOk === false" type="danger" size="small">后端未启动（8000 端口）</el-tag>
        <el-tag v-else type="info" size="small">检测中…</el-tag>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}
.logo {
  padding: 16px;
  font-weight: 600;
  color: #409eff;
}
.menu {
  border-right: none;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #eee;
}
.title {
  font-size: 16px;
  font-weight: 600;
}
</style>
