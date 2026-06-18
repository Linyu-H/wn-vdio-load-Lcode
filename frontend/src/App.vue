<script setup>
import { onMounted } from 'vue'
import AppHeader from './components/AppHeader.vue'
import HistoryDrawer from './components/HistoryDrawer.vue'
import { useAppStore } from './stores/app'
import { api } from './api'

const store = useAppStore()

async function handleRedownload(url) {
  try {
    const res = await api.parseInfo(url)
    if (res.code === 0) store.setVideoInfo(res.data)
  } catch (err) {
    alert('解析失败：' + err.message)
  }
}

// 恢复登录会话
onMounted(async () => {
  if (store.token && !store.user) {
    try {
      const res = await api.me()
      if (res.code === 0) store.setAuth(store.token, res.data)
    } catch {
      store.logout()
    }
  }
})
</script>

<template>
  <div class="app-shell">
    <AppHeader />
    <router-view v-slot="{ Component }">
      <transition name="page" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
    <HistoryDrawer @redownload="handleRedownload" />
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(1100px 560px at 50% -10%, color-mix(in srgb, var(--accent) 12%, transparent), transparent 65%),
    radial-gradient(720px 420px at 0% 8%, color-mix(in srgb, var(--brand-400) 8%, transparent), transparent 60%),
    radial-gradient(820px 480px at 100% 0%, color-mix(in srgb, var(--brand-300) 9%, transparent), transparent 62%),
    var(--bg-app);
}

.page-enter-active,
.page-leave-active {
  transition: opacity 0.28s var(--ease-out), transform 0.28s var(--ease-out);
}
.page-enter-from { opacity: 0; transform: translateY(10px); }
.page-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
