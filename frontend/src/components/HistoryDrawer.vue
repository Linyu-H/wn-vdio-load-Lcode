<template>
  <transition name="drawer">
    <div v-if="isOpen" class="drawer-overlay" @click="close">
      <div class="drawer-panel" @click.stop>
        <div class="drawer-header">
          <h3>📋 下载历史</h3>
          <button @click="close" class="close-btn">×</button>
        </div>

        <div class="drawer-content">
          <div v-if="history.length === 0" class="empty-history">
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
                    🔄 重新下载
                  </button>
                  <button @click="deleteItem(item.id)" class="btn-mini btn-danger">
                    🗑️ 删除
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="history.length > 0" class="drawer-footer">
          <button @click="clearAll" class="btn-secondary">
            清空全部历史
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
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
}

.drawer-panel {
  width: 100%;
  max-width: 450px;
  height: 100%;
  background: var(--bg-card);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  border-bottom: 2px solid var(--border-color);
}

.drawer-header h3 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.close-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-primary);
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background: var(--accent-primary);
  color: white;
  transform: rotate(90deg);
}

.drawer-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.empty-history {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-secondary);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.history-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
}

.history-item:hover {
  transform: translateX(-4px);
  box-shadow: var(--shadow-sm);
}

.history-thumbnail {
  width: 120px;
  height: 68px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-card);
}

.history-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.history-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-title {
  font-size: 14px;
  font-weight: 500;
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
  color: var(--text-secondary);
}

.history-actions {
  display: flex;
  gap: 8px;
  margin-top: auto;
}

.btn-mini {
  padding: 6px 12px;
  font-size: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  transition: all 0.2s ease;
}

.btn-mini:hover {
  border-color: var(--accent-primary);
  background: var(--accent-primary);
  color: white;
}

.btn-mini.btn-danger:hover {
  border-color: #ff6b6b;
  background: #ff6b6b;
  color: white;
}

.drawer-footer {
  padding: 16px 24px;
  border-top: 2px solid var(--border-color);
}

.drawer-footer .btn-secondary {
  width: 100%;
  padding: 12px;
  background: var(--bg-primary);
  color: var(--text-primary);
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.drawer-footer .btn-secondary:hover {
  background: #ff6b6b;
  color: white;
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.3s ease;
}

.drawer-enter-active .drawer-panel,
.drawer-leave-active .drawer-panel {
  transition: transform 0.3s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.drawer-enter-from .drawer-panel,
.drawer-leave-to .drawer-panel {
  transform: translateX(100%);
}

@media (max-width: 768px) {
  .drawer-panel {
    max-width: 100%;
  }

  .history-thumbnail {
    width: 80px;
    height: 45px;
  }
}
</style>
