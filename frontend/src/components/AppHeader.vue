<template>
  <header class="app-header">
    <div class="header-left">
      <VideoLogo />
      <span class="brand-name">vdio-analyze-lcode</span>
    </div>
    <div class="header-right">
      <button @click="toggleHistory" class="icon-btn" title="历史记录">
        📋
      </button>
      <button @click="toggleTheme" class="icon-btn" title="切换主题">
        {{ isDark ? '☀️' : '🌙' }}
      </button>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useAppStore } from '../stores/app'
import VideoLogo from './VideoLogo.vue'

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
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 32px;
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.header-right {
  display: flex;
  gap: 8px;
}

.icon-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  transition: all 0.2s ease;
}

.icon-btn:hover {
  transform: scale(1.1);
  background: var(--accent-primary);
}

@media (max-width: 768px) {
  .app-header {
    padding: 16px 20px;
  }

  .brand-name {
    font-size: 16px;
  }

  .icon-btn {
    width: 36px;
    height: 36px;
    font-size: 18px;
  }
}
</style>
