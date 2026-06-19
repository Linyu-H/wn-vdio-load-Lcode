const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function parseJsonResponse(res) {
  let data

  try {
    data = await res.json()
  } catch {
    throw new Error('服务器返回了无法解析的响应')
  }

  if (!res.ok) {
    throw new Error(data.detail || data.msg || `请求失败：${res.status}`)
  }

  return data
}

export const api = {
  authHeaders() {
    const token = localStorage.getItem('token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  },

  // ── 账号（仅管理员登录用于后台维护）──
  async login(username, password) {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    })
    return parseJsonResponse(res)
  },

  async me() {
    const res = await fetch(`${API_BASE}/api/auth/me`, { headers: this.authHeaders() })
    return parseJsonResponse(res)
  },

  // ── VIP 自动解析 + 上下集 ──
  async resolveVip(url) {
    const res = await fetch(`${API_BASE}/api/vip/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    })
    return parseJsonResponse(res)
  },

  async reportVipFailure(sourceId) {
    try {
      await fetch(`${API_BASE}/api/vip/report-failure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: sourceId })
      })
    } catch { /* 静默 */ }
  },

  async getEpisodes(url) {
    const res = await fetch(`${API_BASE}/api/episodes?url=${encodeURIComponent(url)}`)
    return parseJsonResponse(res)
  },

  // ── 管理端源 CRUD ──
  async adminListSources() {
    const res = await fetch(`${API_BASE}/api/admin/sources`, { headers: this.authHeaders() })
    return parseJsonResponse(res)
  },

  async adminAddSource(name, url, enabled = true) {
    const res = await fetch(`${API_BASE}/api/admin/sources`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...this.authHeaders() },
      body: JSON.stringify({ name, url, enabled })
    })
    return parseJsonResponse(res)
  },

  async adminUpdateSource(id, fields) {
    const res = await fetch(`${API_BASE}/api/admin/sources/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...this.authHeaders() },
      body: JSON.stringify(fields)
    })
    return parseJsonResponse(res)
  },

  async adminDeleteSource(id) {
    const res = await fetch(`${API_BASE}/api/admin/sources/${id}`, {
      method: 'DELETE',
      headers: this.authHeaders()
    })
    return parseJsonResponse(res)
  },

  // ── 管理端多平台 Cookie ──
  async adminListCookies() {
    const res = await fetch(`${API_BASE}/api/admin/cookies`, { headers: this.authHeaders() })
    return parseJsonResponse(res)
  },

  async adminSetCookie(platform, content) {
    const res = await fetch(`${API_BASE}/api/admin/cookies/${platform}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...this.authHeaders() },
      body: JSON.stringify({ content })
    })
    return parseJsonResponse(res)
  },

  async adminToggleCookie(platform, enabled) {
    const res = await fetch(`${API_BASE}/api/admin/cookies/${platform}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...this.authHeaders() },
      body: JSON.stringify({ enabled })
    })
    return parseJsonResponse(res)
  },

  async adminDeleteCookie(platform) {
    const res = await fetch(`${API_BASE}/api/admin/cookies/${platform}`, {
      method: 'DELETE',
      headers: this.authHeaders()
    })
    return parseJsonResponse(res)
  },

  async parseInfo(url, options = {}) {
    const { forceVip = false } = options
    const res = await fetch(`${API_BASE}/api/info`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, force_vip: forceVip })
    })
    return parseJsonResponse(res)
  },

  async createDownload(url, quality = '1080', audio_only = false, vip_source_id = null) {
    const res = await fetch(`${API_BASE}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, quality, audio_only, vip_source_id })
    })
    return res.json()
  },

  getFileUrl(taskId) {
    return `${API_BASE}/api/file/${taskId}`
  },

  getWsUrl(taskId) {
    const wsBase = API_BASE.replace('http', 'ws')
    return `${wsBase}/api/ws/${taskId}`
  },

  async getHistory(limit = 50) {
    const res = await fetch(`${API_BASE}/api/history?limit=${limit}`)
    return res.json()
  },

  async deleteHistory(taskId) {
    const res = await fetch(`${API_BASE}/api/history/${taskId}`, {
      method: 'DELETE'
    })
    return res.json()
  },

  async clearHistory() {
    const res = await fetch(`${API_BASE}/api/history`, {
      method: 'DELETE'
    })
    return res.json()
  }
}
