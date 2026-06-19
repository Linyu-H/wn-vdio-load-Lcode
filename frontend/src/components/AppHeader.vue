<template>
  <header class="app-header">
    <div class="header-inner">
      <div class="header-left">
         <img class="brand-mark" src="/vdio-logo.png" alt="logo" />
        <span class="brand-name">analyze vdio loader <span class="brand-code">Lcode</span></span>
      </div>

      <div class="header-right">
        <button @click="toggleHistory" class="icon-btn" title="下载历史" aria-label="下载历史">
          <Icon name="history" :size="19" />
        </button>
        <button @click="toggleTheme" class="icon-btn" :title="themeTitle" aria-label="切换主题">
          <Icon :name="themeIcon" :size="19" />
        </button>
        <button v-if="isAdmin" @click="goAdmin" class="text-btn" title="管理端">
          <Icon name="shield" :size="16" /> 管理端
        </button>
        <button v-if="isAdmin" @click="logout" class="text-btn ghost" :title="`退出 ${store.user?.username}`">
          {{ store.user?.username }}
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import Icon from './Icon.vue'

const store = useAppStore()
const router = useRouter()
const themeIcon = computed(() => ({ light: 'sun', eyecare: 'eye', dark: 'moon' }[store.theme] || 'sun'))
const themeTitle = computed(() => ({
  light: '当前：浅蓝 · 点击切换护眼',
  eyecare: '当前：护眼 · 点击切换深色',
  dark: '当前：深色 · 点击切换浅蓝',
}[store.theme] || '切换主题'))
const isAdmin = computed(() => store.isAdmin)

function toggleTheme() {
  store.toggleTheme()
}

function toggleHistory() {
  store.toggleHistoryDrawer()
}

function goAdmin() { router.push('/admin') }
function logout() {
  if (confirm('确定退出登录？')) {
    store.logout()
    router.push('/')
  }
}
</script>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: color-mix(in srgb, var(--bg-app) 72%, transparent);
  backdrop-filter: saturate(180%) blur(16px);
  -webkit-backdrop-filter: saturate(180%) blur(16px);
  border-bottom: 1px solid color-mix(in srgb, var(--border) 60%, transparent);
}

.header-inner {
  max-width: 1180px;
  margin: 0 auto;
  padding: 12px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--accent-gradient);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: -0.04em;
  box-shadow: var(--shadow-xs);
}

.brand-name {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text-secondary);
}

.brand-code { color: var(--text-tertiary); }

.header-right {
  display: flex;
  gap: 6px;
}

.icon-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
}

.icon-btn:hover {
  background: var(--bg-hover);
  color: var(--accent);
  border-color: var(--border);
}

.icon-btn:active { transform: translateY(1px); }

.text-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 14px;
  border-radius: var(--radius-sm);
  font-size: 13.5px;
  font-weight: 600;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
}
.text-btn:hover { background: var(--bg-hover); color: var(--accent); border-color: var(--border-strong); }
.text-btn.solid {
  background: var(--accent);
  color: var(--text-on-brand);
  border-color: transparent;
}
.text-btn.solid:hover { background: var(--accent-hover); color: var(--text-on-brand); }
.text-btn.ghost { color: var(--text-primary); }

@media (max-width: 640px) {
  .header-inner { padding: 10px 16px; }
  .brand-name { display: none; }
}
</style>
