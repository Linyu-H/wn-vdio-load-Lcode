import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  const THEMES = ['light', 'eyecare', 'dark']
  const storedTheme = localStorage.getItem('theme')
  const theme = ref(THEMES.includes(storedTheme) ? storedTheme : 'light')
  const videoInfo = ref(null)
  const currentTask = ref(null)
  const history = ref([])
  const historyDrawerOpen = ref(false)
  const parsing = ref(false)
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')

  const isDark = computed(() => theme.value === 'dark')
  const isEyecare = computed(() => theme.value === 'eyecare')
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

  function applyTheme() {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', theme.value)
    }
  }

  function setTheme(t) {
    theme.value = THEMES.includes(t) ? t : 'light'
    localStorage.setItem('theme', theme.value)
    applyTheme()
  }

  // 顺序循环：浅蓝(light) → 护眼(eyecare) → 深色(dark) → 浅蓝
  function toggleTheme() {
    const i = THEMES.indexOf(theme.value)
    setTheme(THEMES[(i + 1) % THEMES.length])
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
  applyTheme()

  return {
    theme,
    isDark,
    isEyecare,
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
    setTheme,
    setVideoInfo,
    setParsing,
    setCurrentTask,
    addHistory,
    setHistory,
    toggleHistoryDrawer
  }
})
