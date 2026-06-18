import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  const theme = ref(localStorage.getItem('theme') || 'light')
  const videoInfo = ref(null)
  const currentTask = ref(null)
  const history = ref([])
  const historyDrawerOpen = ref(false)
  const parsing = ref(false)
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')

  const isDark = computed(() => theme.value === 'dark')
  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  function setAuth(tk, usr) {
    token.value = tk || ''
    user.value = usr || null
    if (tk) localStorage.setItem('token', tk)
    else localStorage.removeItem('token')
  }

  function logout() {
    setAuth('', null)
  }

  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    localStorage.setItem('theme', theme.value)
    document.documentElement.setAttribute('data-theme', theme.value)
  }

  function setVideoInfo(info) {
    videoInfo.value = info
  }

  function setParsing(val) {
    parsing.value = val
  }

  function setCurrentTask(task) {
    currentTask.value = task
  }

  function addHistory(item) {
    history.value.unshift(item)
  }

  function setHistory(items) {
    history.value = items
  }

  function toggleHistoryDrawer() {
    historyDrawerOpen.value = !historyDrawerOpen.value
  }

  // 初始化主题
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', theme.value)
  }

  return {
    theme,
    isDark,
    videoInfo,
    currentTask,
    history,
    historyDrawerOpen,
    parsing,
    user,
    token,
    isLoggedIn,
    isAdmin,
    setAuth,
    logout,
    toggleTheme,
    setVideoInfo,
    setParsing,
    setCurrentTask,
    addHistory,
    setHistory,
    toggleHistoryDrawer
  }
})
