<script setup lang="ts">
// M9 个人画像页（需登录）：标记统计 + 最近收藏 + 最近已读 + 账号设置
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getProfile, updatePassword, updateProfile } from '../api/users'
import TopicTag from '../components/TopicTag.vue'
import { useAuthStore } from '../stores/authStore'
import { useFilterStore } from '../stores/filterStore'
import type { ProfileStats } from '../types'

const router = useRouter()
const auth = useAuthStore()
const filter = useFilterStore()
const profile = ref<ProfileStats | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    profile.value = await getProfile()
  } catch (e) {
    console.error('画像加载失败', e)
    ElMessage.error('画像加载失败')
  } finally {
    loading.value = false
  }
})

function goPaper(id: number) {
  router.push(`/papers/${id}`)
}

// 已读卡片 / 「查看全部」点击 → 论文列表页（重置筛选，只看已读）
function goReadList() {
  filter.reset()
  filter.marks = 'read'
  router.push('/')
}

// 收藏卡片 / 「查看全部」点击 → 论文列表页（重置筛选，只看收藏）
function goBookmarkList() {
  filter.reset()
  filter.marks = 'bookmark'
  router.push('/')
}

// ---- M9 反馈：账号设置 ----

const profileDialog = ref(false)
const profileForm = ref({ username: '', email: '' })
const profileSaving = ref(false)

function openProfileDialog() {
  profileForm.value = {
    username: profile.value?.username || '',
    email: profile.value?.email || '',
  }
  profileDialog.value = true
}

async function saveProfile() {
  profileSaving.value = true
  try {
    const user = await updateProfile({
      username: profileForm.value.username.trim(),
      email: profileForm.value.email.trim() || null,
    })
    auth.user = user
    localStorage.setItem('auth_user', JSON.stringify(user))
    if (profile.value) profile.value.username = user.username
    ElMessage.success('资料已更新')
    profileDialog.value = false
  } catch (e) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '保存失败')
  } finally {
    profileSaving.value = false
  }
}

const pwdDialog = ref(false)
const pwdForm = ref({ old: '', next: '', confirm: '' })
const pwdSaving = ref(false)

async function savePassword() {
  if (!pwdForm.value.old || !pwdForm.value.next) {
    ElMessage.warning('请填写完整')
    return
  }
  if (pwdForm.value.next !== pwdForm.value.confirm) {
    ElMessage.warning('两次新密码不一致')
    return
  }
  pwdSaving.value = true
  try {
    await updatePassword(pwdForm.value.old, pwdForm.value.next)
    ElMessage.success('密码已修改')
    pwdDialog.value = false
    pwdForm.value = { old: '', next: '', confirm: '' }
  } catch (e) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '修改失败')
  } finally {
    pwdSaving.value = false
  }
}
</script>

<template>
  <div v-loading="loading" class="profile-page">
    <template v-if="profile">
      <h2 class="page-title">
        {{ profile.username }} 的阅读画像
        <el-button size="small" @click="openProfileDialog">修改资料</el-button>
        <el-button size="small" @click="pwdDialog = true">修改密码</el-button>
      </h2>

      <!-- 统计卡片 -->
      <div class="stats">
        <div class="stat-card clickable" title="查看全部收藏论文" @click="goBookmarkList">
          <div class="stat-num mono">{{ profile.counts.bookmark }}</div>
          <div class="stat-label">⭐ 收藏 ›</div>
        </div>
        <div class="stat-card clickable" title="查看全部已读论文" @click="goReadList">
          <div class="stat-num mono">{{ profile.counts.read }}</div>
          <div class="stat-label">✓ 已读 ›</div>
        </div>
        <div class="stat-card">
          <div class="stat-num mono">{{ profile.counts.read_later }}</div>
          <div class="stat-label">📌 稍后读</div>
        </div>
      </div>

      <!-- 最近收藏 -->
      <el-card class="card" shadow="never">
        <template #header>
          <div class="card-head">
            <span class="card-title">最近收藏</span>
            <el-link type="primary" @click="goBookmarkList">查看全部 ›</el-link>
          </div>
        </template>
        <ul v-if="profile.recent.length" class="recent">
          <li v-for="p in profile.recent" :key="p.id">
            <el-link type="primary" @click="goPaper(p.id)">{{ p.title }}</el-link>
            <span v-if="p.venue" class="muted">· {{ p.venue.short_name }} {{ p.year ?? '' }}</span>
            <span class="topics-inline">
              <TopicTag v-for="t in p.topics" :key="t.slug" :topic="t" />
            </span>
          </li>
        </ul>
        <p v-else class="empty">暂无收藏</p>
      </el-card>

      <!-- 最近已读 -->
      <el-card class="card" shadow="never">
        <template #header>
          <div class="card-head">
            <span class="card-title">最近已读</span>
            <el-link type="primary" @click="goReadList">查看全部 ›</el-link>
          </div>
        </template>
        <ul v-if="profile.recent_read.length" class="recent">
          <li v-for="p in profile.recent_read" :key="p.id">
            <el-link type="primary" @click="goPaper(p.id)">{{ p.title }}</el-link>
            <span v-if="p.venue" class="muted">· {{ p.venue.short_name }} {{ p.year ?? '' }}</span>
            <span class="topics-inline">
              <TopicTag v-for="t in p.topics" :key="t.slug" :topic="t" />
            </span>
          </li>
        </ul>
        <p v-else class="empty">还没有已读论文——打开论文详情页点「标记已读」即可</p>
      </el-card>

      <!-- M9 反馈：账号设置对话框 -->
      <el-dialog v-model="profileDialog" title="修改资料" width="420px">
        <el-form label-position="top">
          <el-form-item label="用户名">
            <el-input v-model="profileForm.username" placeholder="2-64 位，字母数字.-_">
            </el-input>
          </el-form-item>
          <el-form-item label="邮箱（可选）">
            <el-input v-model="profileForm.email" placeholder="user@example.com" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="profileDialog = false">取消</el-button>
          <el-button type="primary" :loading="profileSaving" @click="saveProfile">保存</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="pwdDialog" title="修改密码" width="420px">
        <el-form label-position="top">
          <el-form-item label="当前密码">
            <el-input v-model="pwdForm.old" type="password" show-password />
          </el-form-item>
          <el-form-item label="新密码（至少 6 位）">
            <el-input v-model="pwdForm.next" type="password" show-password />
          </el-form-item>
          <el-form-item label="确认新密码">
            <el-input v-model="pwdForm.confirm" type="password" show-password
                      @keyup.enter="savePassword" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="pwdDialog = false">取消</el-button>
          <el-button type="primary" :loading="pwdSaving" @click="savePassword">确认修改</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<style scoped>
.profile-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 8px 24px 32px;
}
.page-title {
  font-size: 20px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.stats {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}
.stat-card {
  flex: 1;
  background: var(--brand-surface);
  border: 1px solid var(--brand-border);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
}
.stat-card.clickable {
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
}
.stat-card.clickable:hover {
  border-color: var(--brand-primary);
  transform: translateY(-1px);
}
.stat-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--brand-text);
}
.stat-label {
  margin-top: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.card {
  margin-bottom: 16px;
}
.card-title {
  font-weight: 600;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.recent {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.recent li {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.topics-inline {
  margin-left: auto;
  display: flex;
  gap: 4px;
}
.empty {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}
.muted {
  color: var(--el-text-color-secondary);
}
</style>
