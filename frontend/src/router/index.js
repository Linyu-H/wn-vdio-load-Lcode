import { createRouter, createWebHistory } from 'vue-router'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import AdminView from '../views/AdminView.vue'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/login', name: 'login', component: LoginView },
  { path: '/admin', name: 'admin', component: AdminView, meta: { requiresAdmin: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

// 路由守卫：访问 admin 需已登录且为管理员
router.beforeEach(async (to) => {
  const store = useAppStore()

  // 有 token 但还没拉到用户信息时，先恢复会话
  if (store.token && !store.user) {
    try {
      const res = await api.me()
      if (res.code === 0) store.setAuth(store.token, res.data)
    } catch {
      store.logout()
    }
  }

  if (to.meta.requiresAdmin) {
    if (!store.isLoggedIn) return { name: 'login', query: { redirect: to.fullPath } }
    if (!store.isAdmin) return { name: 'home' }
  }
  return true
})

export default router
