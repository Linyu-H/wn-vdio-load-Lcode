<template>
  <transition name="drawer">
    <div v-if="isOpen" class="drawer-overlay" @click="close">
      <div class="drawer-panel" @click.stop>
        <div class="drawer-header">
          <h3><Icon name="history" :size="18" /> 下载历史</h3>
          <button @click="close" class="close-btn" aria-label="关闭">
            <Icon name="close" :size="18" />
          </button>
        </div>

        <div class="drawer-content">
          <div v-if="history.length === 0" class="empty-history">
            <div class="empty-history-icon"><Icon name="clock" :size="26" :stroke-width="1.5" /></div>
            <p>暂无下载记录</p>
          </div>

          <div v-else class="history-list">
            <div
              v-for="item in history"
              :key="item.id"
              class="history-item"
            >
              <div v-if="item.thumbnail" class="history-thumbnail">
                <img :src="item.thumbnail" :alt="item.title" />
              </div>
              <div class="history-info">
                <h4 class="history-title">{{ item.title }}</h4>
                <div class="history-meta">
                  <span>{{ getPlatformIcon(item.platform) }} {{ item.platform }}</span>
                  <span>{{ formatTime(item.created_at) }}</span>
                </div>
                <div class="history-actions">
                  <button @click="redownload(item)" class="btn-mini">
                    <Icon name="refresh" :size="13" /> 重新下载
                  </button>
                  <button @click="deleteItem(item.id)" class="btn-mini btn-danger">
                    <Icon name="trash" :size="13" /> 删除
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="history.length > 0" class="drawer-footer">
          <button @click="clearAll" class="btn-secondary">
            <Icon name="trash" :size="15" /> 清空全部历史
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed, watch, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { getPlatformIcon } from '../utils/platform'
import Icon from './Icon.vue'

const store = useAppStore()
const isOpen = computed(() => store.historyDrawerOpen)
const history = computed(() => store.history)

const emit = defineEmits(['redownload'])

onMounted(async () => {
  await loadHistory()
})

async function loadHistory() {
  try {
    const res = await api.getHistory()
    if (res.code === 0) {
      store.setHistory(res.data)
    }
  } catch (err) {
    console.error('加载历史记录失败:', err)
  }
}

function close() {
  store.toggleHistoryDrawer()
}

function redownload(item) {
  emit('redownload', item.url)
  close()
}

async function deleteItem(taskId) {
  if (!confirm('确定删除此记录？')) return

  try {
    await api.deleteHistory(taskId)
    await loadHistory()
  } catch (err) {
    alert('删除失败：' + err.message)
  }
}

async function clearAll() {
  if (!confirm('确定清空所有历史记录？')) return

  try {
    await api.clearHistory()
    await loadHistory()
  } catch (err) {
    alert('清空失败：' + err.message)
  }
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now - date
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return date.toLocaleDateString()
}

watch(isOpen, (open) => {
  if (open) {
    loadHistory()
  }
})
</script>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(40, 28, 14, 0.42);
  backdrop-filter: blur(3px);
  -webkit-backdrop-filter: blur(3px);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
}

.drawer-panel {
  width: 100%;
  max-width: 440px;
  height: 100%;
  background: var(--bg-card);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-xl);
  border-left: 1px solid var(--border);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 22px;
  border-bottom: 1px solid var(--border);
}

.drawer-header h3 {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin: 0;
}

.drawer-header h3 :deep(.icon) { color: var(--accent); }

.close-btn {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.drawer-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.empty-history {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 240px;
  color: var(--text-tertiary);
  font-size: 14px;
}

.empty-history-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease);
}

.history-item:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-sm);
}

.history-thumbnail {
  width: 116px;
  height: 66px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-inset);
}

.history-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.history-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.history-title {
  font-size: 13.5px;
  font-weight: 600;
  margin: 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.history-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.history-actions {
  display: flex;
  gap: 8px;
  margin-top: auto;
}

.btn-mini {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 11px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
}

.btn-mini:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}

.btn-mini.btn-danger:hover {
  border-color: var(--danger);
  color: var(--danger);
  background: var(--danger-soft);
}

.drawer-footer {
  padding: 16px 22px;
  border-top: 1px solid var(--border);
}

.drawer-footer .btn-secondary {
  width: 100%;
}

.drawer-footer .btn-secondary:hover {
  border-color: var(--danger);
  color: var(--danger);
  background: var(--danger-soft);
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.3s var(--ease);
}

.drawer-enter-active .drawer-panel,
.drawer-leave-active .drawer-panel {
  transition: transform 0.32s var(--ease-out);
}

.drawer-enter-from,
.drawer-leave-to { opacity: 0; }

.drawer-enter-from .drawer-panel,
.drawer-leave-to .drawer-panel { transform: translateX(100%); }

@media (max-width: 768px) {
  .drawer-panel { max-width: 100%; }
  .history-thumbnail { width: 88px; height: 50px; }
}
</style>
