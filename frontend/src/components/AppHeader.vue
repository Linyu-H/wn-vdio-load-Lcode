<template>
  <header class="app-header">
    <div class="header-inner">
      <div class="header-left">
        <span class="brand-mark">avl</span>
        <span class="brand-name">analyze vdio loader <span class="brand-code">Lcode</span></span>
      </div>

      <div class="header-right">
        <button @click="toggleHistory" class="icon-btn" title="下载历史" aria-label="下载历史">
          <Icon name="history" :size="19" />
        </button>
        <button @click="toggleTheme" class="icon-btn" :title="isDark ? '切换浅色' : '切换深色'" aria-label="切换主题">
          <Icon :name="isDark ? 'sun' : 'moon'" :size="19" />
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useAppStore } from '../stores/app'
import Icon from './Icon.vue'

const store = useAppStore()
const isDark = computed(() => store.isDark)

function toggleTheme() {
  store.toggleTheme()
}

function toggleHistory() {
  store.toggleHistoryDrawer()
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

@media (max-width: 640px) {
  .header-inner { padding: 10px 16px; }
  .brand-name { display: none; }
}
</style>
