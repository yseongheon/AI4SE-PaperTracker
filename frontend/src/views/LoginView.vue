<script setup lang="ts">
// M9 登录/注册页：切换表单、错误提示、登录后跳 redirect 或首页
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/authStore'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const email = ref('')
const password = ref('')
const confirm = ref('')
const loading = ref(false)

async function submit() {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (mode.value === 'register' && password.value !== confirm.value) {
    ElMessage.warning('两次密码不一致')
    return
  }
  loading.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(username.value.trim(), password.value)
      ElMessage.success(`欢迎回来，${auth.user?.username}`)
    } else {
      await auth.register(username.value.trim(), password.value, email.value.trim() || undefined)
      ElMessage.success(`注册成功，欢迎 ${auth.user?.username}`)
    }
    router.push(String(route.query.redirect || '/'))
  } catch (e) {
    const status = (e as { response?: { status?: number; data?: { detail?: string } } })?.response
    ElMessage.error(status?.data?.detail || '操作失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="never">
      <div class="login-logo">
        <span class="logo-mark">AI4SE</span>
        <span class="logo-sub">PaperTracker · 课题组账号</span>
      </div>
      <el-tabs v-model="mode" stretch>
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名 / 邮箱">
          <el-input v-model="username" placeholder="用户名（注册）或用户名/邮箱（登录）" clearable />
        </el-form-item>
        <el-form-item v-if="mode === 'register'" label="邮箱（可选）">
          <el-input v-model="email" placeholder="用于找回等场景" clearable />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            show-password
            :placeholder="mode === 'register' ? '至少 6 位' : '密码'"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-form-item v-if="mode === 'register'" label="确认密码">
          <el-input v-model="confirm" type="password" show-password @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" class="submit" :loading="loading" @click="submit">
          {{ mode === 'login' ? '登录' : '注册并登录' }}
        </el-button>
      </el-form>
      <p class="hint">未登录也可浏览论文；收藏 / 已读 / 稍后读与个人画像需要登录</p>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  padding-top: 48px;
}
.login-card {
  width: 400px;
  padding: 8px 12px;
}
.login-logo {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  margin-bottom: 12px;
}
.logo-mark {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 24px;
  color: var(--brand-text);
}
.logo-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  letter-spacing: 0.1em;
}
.submit {
  width: 100%;
}
.hint {
  margin-top: 14px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  text-align: center;
}
</style>
