<template>
  <header class="app-header">
    <div class="header-inner">
      <div class="header-left">
        <VideoLogo />
        <div class="brand-text">
          <span class="brand-name">vdio</span>
          <span class="brand-sub">视频解析下载平台</span>
        </div>
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
import VideoLogo from './VideoLogo.vue'
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
  background: color-mix(in srgb, var(--bg-card) 82%, transparent);
  backdrop-filter: saturate(180%) blur(16px);
  -webkit-backdrop-filter: saturate(180%) blur(16px);
  border-bottom: 1px solid var(--border);
}

.header-inner {
  max-width: 1600px;
  margin: 0 auto;
  padding: 14px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 13px;
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
}

.brand-name {
  font-size: 19px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--text-primary);
}

.brand-sub {
  font-size: 11.5px;
  font-weight: 500;
  color: var(--text-tertiary);
  letter-spacing: 0.01em;
}

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

@media (max-width: 768px) {
  .header-inner { padding: 12px 18px; }
  .brand-sub { display: none; }
}
</style>
