<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import Icon from '../components/Icon.vue'

const store = useAppStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  if (!username.value.trim() || !password.value) {
    error.value = '请填写用户名和密码'
    return
  }
  loading.value = true
  try {
    const res = await api.login(username.value.trim(), password.value)
    if (res.code !== 0) throw new Error(res.detail || res.msg || '登录失败')
    if (res.data.role !== 'admin') throw new Error('该账号无管理权限')
    store.setAuth(res.data.token, { username: res.data.username, role: res.data.role })
    router.push(route.query.redirect || '/admin')
  } catch (err) {
    error.value = err.message || '操作失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth-wrap">
    <div class="auth-card card">
      <div class="auth-head">
        <div class="auth-mark"><Icon name="shield" :size="22" /></div>
        <h1>管理员登录</h1>
        <p>仅供后台维护 · analyze vdio loader Lcode</p>
      </div>

      <form @submit.prevent="submit" class="auth-form">
        <label class="field">
          <span><Icon name="user" :size="15" /> 用户名</span>
          <input v-model="username" type="text" autocomplete="username" placeholder="至少 3 个字符" />
        </label>
        <label class="field">
          <span><Icon name="shield" :size="15" /> 密码</span>
          <input v-model="password" type="password" autocomplete="current-password" placeholder="至少 6 个字符" @keydown.enter="submit" />
        </label>

        <p v-if="error" class="auth-error"><Icon name="alert" :size="14" /> {{ error }}</p>

        <button type="submit" class="btn-primary submit" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? '处理中…' : '登录' }}
        </button>
      </form>

      <router-link to="/" class="back-link">← 返回首页</router-link>
    </div>
  </main>
</template>

<style scoped>
.auth-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
}

.auth-card {
  width: 100%;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  gap: 22px;
  box-shadow: var(--shadow-lg);
  animation: rise 0.45s var(--ease-out) both;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

.auth-head { text-align: center; }

.auth-mark {
  width: 52px;
  height: 52px;
  margin: 0 auto 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  background: var(--accent-soft);
  color: var(--accent);
}

.auth-head h1 { font-size: 22px; font-weight: 800; letter-spacing: -0.02em; margin: 0; }
.auth-head p { font-size: 13px; color: var(--text-tertiary); margin: 4px 0 0; }

.auth-form { display: flex; flex-direction: column; gap: 14px; }

.field { display: flex; flex-direction: column; gap: 7px; }
.field span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}
.field input { width: 100%; }

.auth-error {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--danger);
  margin: 0;
}

.submit { width: 100%; padding: 12px; margin-top: 2px; }

.spinner {
  width: 15px; height: 15px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.back-link {
  text-align: center;
  font-size: 13px;
  color: var(--text-tertiary);
  text-decoration: none;
}
.back-link:hover { color: var(--accent); }
</style>
