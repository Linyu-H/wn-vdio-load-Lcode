<script setup>
import { ref } from 'vue'
import AppHeader from './components/AppHeader.vue'
import InputPanel from './components/InputPanel.vue'
import PreviewPanel from './components/PreviewPanel.vue'
import HistoryDrawer from './components/HistoryDrawer.vue'
import { useAppStore } from './stores/app'
import { api } from './api'

const store = useAppStore()
const inputRef = ref(null)

async function handleRedownload(url) {
  try {
    const res = await api.parseInfo(url)
    if (res.code === 0) {
      store.setVideoInfo(res.data)
    }
  } catch (err) {
    alert('解析失败：' + err.message)
  }
}
</script>

<template>
  <div class="app-container">
    <AppHeader />

    <main class="main-content">
      <div class="split-layout">
        <div class="left-panel">
          <InputPanel ref="inputRef" />
        </div>

        <div class="right-panel">
          <PreviewPanel />
        </div>
      </div>
    </main>

    <HistoryDrawer @redownload="handleRedownload" />
  </div>
</template>

<style scoped>
.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

.main-content {
  flex: 1;
  padding: 24px 32px;
  max-width: 1600px;
  width: 100%;
  margin: 0 auto;
}

.split-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  height: 100%;
  min-height: 600px;
}

.left-panel,
.right-panel {
  height: 100%;
}

@media (max-width: 1024px) {
  .split-layout {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .main-content {
    padding: 20px;
  }

  .left-panel,
  .right-panel {
    height: auto;
    min-height: 400px;
  }
}

@media (max-width: 768px) {
  .main-content {
    padding: 16px;
  }

  .split-layout {
    gap: 16px;
  }
}
</style>
