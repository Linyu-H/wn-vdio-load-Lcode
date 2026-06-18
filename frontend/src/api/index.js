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
