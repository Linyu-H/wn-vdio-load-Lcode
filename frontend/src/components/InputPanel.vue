<template>
  <div class="input-panel card">
    <h2>📥 输入视频链接</h2>
    <div class="url-input-wrapper">
      <textarea
        v-model="urls"
        @input="handleInput"
        placeholder="粘贴视频链接，支持批量（每行一个）&#10;支持拖拽文本文件导入"
        class="url-textarea"
        rows="8"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
        :class="{ dragging: isDragging }"
      ></textarea>
      <div v-if="urlList.length > 0" class="url-tags">
        <div
          v-for="(item, idx) in urlList"
          :key="idx"
          class="url-tag"
          :class="{ invalid: !item.valid }"
        >
          <span class="platform-logo-wrap">
            <img
              v-if="item.logo && !item.logoBroken"
              :src="item.logo"
              :alt="`${item.host || '网站'} logo`"
              class="platform-logo"
              @error="markLogoBroken(item)"
            />
            <span v-else class="platform-icon">{{ item.icon }}</span>
          </span>
          <span class="url-text" :title="item.url">{{ truncate(item.url, 30) }}</span>
          <button @click="removeUrl(idx)" class="remove-btn">×</button>
          <button v-if="item.valid" @click="parseSingle(item.url)" class="parse-btn" :disabled="isParsing">
            {{ isParsing ? '…' : '🔍' }}
          </button>
        </div>
      </div>
    </div>

    <div class="action-buttons">
      <button @click="parseAll" class="btn-primary" :disabled="!hasValidUrls || isParsing">
        {{ isParsing ? '解析中...' : '解析全部' }}
      </button>
      <button @click="pasteFromClipboard" class="btn-secondary">
        📋 从剪贴板导入
      </button>
      <button @click="clearAll" class="btn-secondary" :disabled="urlList.length === 0">
        🗑️ 清空
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { detectPlatformFromUrl, getFaviconUrl, getPlatformIcon, getUrlHost, isValidUrl } from '../utils/platform'
import { api } from '../api'
import { useAppStore } from '../stores/app'

const VIP_HINT_HOSTS = ['bilibili.com', 'b23.tv', 'v.qq.com', 'm.v.qq.com', 'iqiyi.com', 'iq.com', 'youku.com', 'mgtv.com', 'tudou.com', 'tv.sohu.com', 'film.sohu.com', 'le.com', 'pptv.com', 'wasu.cn', 'acfun.cn', '1905.com']

const store = useAppStore()
const urls = ref('')
const urlList = ref([])
const isDragging = ref(false)
const isParsing = ref(false)

const emit = defineEmits(['parse-success'])

const hasValidUrls = computed(() => urlList.value.some(u => u.valid))

function handleInput() {
  const lines = urls.value.split('\n').filter(line => line.trim())
  urlList.value = lines.map((url) => {
    const trimmed = url.trim()
    const platform = detectPlatformFromUrl(trimmed)
    return {
      url: trimmed,
      valid: isValidUrl(trimmed),
      platform,
      host: getUrlHost(trimmed),
      logo: getFaviconUrl(trimmed),
      logoBroken: false,
      icon: getPlatformIcon(platform)
    }
  })
}

function markLogoBroken(item) {
  item.logoBroken = true
}

function mightNeedVipFallback(url) {
  try {
    const host = new URL(url).hostname.toLowerCase()
    return VIP_HINT_HOSTS.some(item => host.includes(item))
  } catch {
    return false
  }
}

function toFriendlyParseError(err) {
  const message = err?.message || String(err || '未知错误')
  if (message.includes('不支持 VIP 解析模式')) return '当前链接不是会员视频，且无法使用 VIP 解析'
  if (message.includes('VIP 解析源不可用')) return 'VIP 解析源暂时不可用，请稍后重试'
  if (message.includes('服务器返回了无法解析的响应')) return '解析服务返回异常，请稍后重试'
  if (message.includes('timeout') || message.includes('超时')) return '解析超时，请稍后重试'
  return message.replace(/^解析失败[:：]?\s*/, '')
}

function applyParseResult(res) {
  console.debug('[parse] response', res)
  if (res.code !== 0) {
    throw new Error(res.msg || res.detail || '未知错误')
  }
  store.setVideoInfo(res.data)
  emit('parse-success', res.data)
}

function removeUrl(idx) {
  urlList.value.splice(idx, 1)
  urls.value = urlList.value.map(u => u.url).join('\n')
}

async function parseSingle(url, { manageLoading = true, showAlert = true } = {}) {
  if (isParsing.value && manageLoading) return { ok: false, error: '正在解析中' }

  console.info('[parse] start', { url, manageLoading, showAlert })
  if (manageLoading) isParsing.value = true

  try {
    try {
      console.info('[parse] normal request', { url })
      const res = await api.parseInfo(url)
      applyParseResult(res)
      console.info('[parse] normal success', { url })
      return { ok: true }
    } catch (err) {
      console.warn('[parse] normal failed', { url, error: err?.message || err })
      if (!mightNeedVipFallback(url)) throw err

      console.info('[parse] vip fallback request', { url })
      const vipRes = await api.parseInfo(url, { forceVip: true })
      applyParseResult(vipRes)
      console.info('[parse] vip fallback success', { url })
      return { ok: true }
    }
  } catch (err) {
    const error = toFriendlyParseError(err)
    console.error('[parse] failed', { url, error, raw: err })
    if (showAlert) alert('解析失败：' + error)
    return { ok: false, error }
  } finally {
    if (manageLoading) isParsing.value = false
  }
}

async function parseAll() {
  if (isParsing.value) return

  const validUrls = urlList.value.filter(u => u.valid)
  if (validUrls.length === 0) return

  console.info('[parse-all] start', { count: validUrls.length, urls: validUrls.map(item => item.url) })
  isParsing.value = true
  let successCount = 0
  let failedCount = 0

  try {
    const failures = []
    for (const item of validUrls) {
      const result = await parseSingle(item.url, { manageLoading: false, showAlert: false })
      console.info('[parse-all] item result', { url: item.url, result })
      if (result.ok) {
        successCount += 1
      } else {
        failedCount += 1
        failures.push(`${truncate(item.url, 36)}：${result.error || '未知错误'}`)
      }
    }
    parseAll.lastFailures = failures
  } finally {
    isParsing.value = false
  }

  console.info('[parse-all] done', { successCount, failedCount, failures: parseAll.lastFailures || [] })
  if (failedCount > 0) {
    const details = parseAll.lastFailures?.length ? `\n${parseAll.lastFailures.join('\n')}` : ''
    alert(`解析完成：成功 ${successCount} 条，失败 ${failedCount} 条${details}`)
  } else if (validUrls.length > 1) {
    alert(`解析完成：成功 ${successCount} 条`)
  }
}

async function pasteFromClipboard() {
  try {
    const text = await navigator.clipboard.readText()
    if (text) {
      urls.value = text
      handleInput()
    }
  } catch (err) {
    alert('无法访问剪贴板，请手动粘贴')
  }
}

function clearAll() {
  urls.value = ''
  urlList.value = []
  store.setVideoInfo(null)
}

function handleDrop(e) {
  isDragging.value = false
  const files = e.dataTransfer.files
  const text = e.dataTransfer.getData('text')

  if (text) {
    urls.value = text
    handleInput()
    return
  }

  if (files.length > 0) {
    const file = files[0]
    if (file.type === 'text/plain') {
      const reader = new FileReader()
      reader.onload = (ev) => {
        urls.value = ev.target.result
        handleInput()
      }
      reader.readAsText(file)
    }
  }
}

function truncate(str, len) {
  return str.length > len ? str.slice(0, len) + '...' : str
}
</script>

<style scoped>
.input-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.url-input-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.url-textarea {
  width: 100%;
  min-height: 200px;
  resize: vertical;
  font-size: 14px;
  line-height: 1.6;
}

.url-textarea.dragging {
  border-color: var(--accent-primary);
  background: rgba(0, 184, 148, 0.05);
}

.url-tags {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.url-tag {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
  border: 2px solid var(--border-color);
  transition: all 0.2s ease;
}

.url-tag.invalid {
  border-color: #ff6b6b;
  opacity: 0.7;
}

.platform-icon {
  font-size: 18px;
}

.platform-logo-wrap {
  width: 22px;
  height: 22px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
}

.platform-logo {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 6px;
  background: var(--bg-card);
}

.url-text {
  flex: 1;
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.remove-btn, .parse-btn {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: bold;
  background: transparent;
  transition: all 0.2s ease;
}

.remove-btn {
  color: #ff6b6b;
}

.remove-btn:hover {
  background: #ff6b6b;
  color: white;
}

.parse-btn {
  color: var(--accent-primary);
}

.parse-btn:hover {
  background: var(--accent-primary);
  color: white;
}

.action-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.btn-secondary {
  padding: 10px 20px;
  background: var(--bg-primary);
  color: var(--text-primary);
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.btn-secondary:hover {
  background: var(--accent-primary);
  color: white;
  transform: translateY(-2px);
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

@media (max-width: 768px) {
  .action-buttons {
    flex-direction: column;
  }

  .action-buttons button {
    width: 100%;
  }
}
</style>
