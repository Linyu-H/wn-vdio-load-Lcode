<template>
  <div class="input-panel card">
    <div class="panel-head">
      <div class="panel-head-icon"><Icon name="link" :size="18" /></div>
      <div>
        <h2 class="panel-title">输入视频链接</h2>
        <p class="panel-desc">支持批量解析，每行一个链接</p>
      </div>
    </div>

    <div class="url-input-wrapper">
      <textarea
        v-model="urls"
        @input="handleInput"
        placeholder="粘贴视频链接，支持批量（每行一个）&#10;也可拖拽文本文件导入"
        class="url-textarea"
        rows="7"
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
          <span class="url-text" :title="item.url">{{ truncate(item.url, 38) }}</span>
          <button
            v-if="item.valid"
            @click="parseSingle(item.url)"
            class="tag-btn parse"
            :disabled="isParsing"
            title="解析此链接"
          >
            <Icon name="search" :size="15" />
          </button>
          <button @click="removeUrl(idx)" class="tag-btn remove" title="移除">
            <Icon name="close" :size="15" />
          </button>
        </div>
      </div>
    </div>

    <div class="action-buttons">
      <button @click="parseAll" class="btn-primary parse-all" :disabled="!hasValidUrls || isParsing">
        <Icon name="search" :size="16" />
        {{ isParsing ? '解析中…' : '解析全部' }}
      </button>
      <button @click="pasteFromClipboard" class="btn-secondary">
        <Icon name="clipboard" :size="16" />
        剪贴板
      </button>
      <button @click="clearAll" class="btn-secondary" :disabled="urlList.length === 0">
        <Icon name="trash" :size="16" />
        清空
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { detectPlatformFromUrl, getFaviconUrl, getPlatformIcon, getUrlHost, isValidUrl } from '../utils/platform'
import { api } from '../api'
import { useAppStore } from '../stores/app'
import Icon from './Icon.vue'

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
  gap: 20px;
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.panel-head-icon {
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-soft);
  color: var(--accent);
}

.panel-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}

.panel-desc {
  font-size: 12.5px;
  color: var(--text-tertiary);
  margin: 2px 0 0;
}

.url-input-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.url-textarea {
  width: 100%;
  min-height: 180px;
  resize: vertical;
  line-height: 1.65;
}

.url-textarea.dragging {
  border-color: var(--accent);
  background: var(--accent-soft);
  box-shadow: 0 0 0 3px var(--accent-ring);
}

.url-tags {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 220px;
  overflow-y: auto;
  padding-right: 4px;
}

.url-tag {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px 9px 12px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  transition: border-color var(--dur) var(--ease), background var(--dur) var(--ease);
}

.url-tag:hover { border-color: var(--border-strong); }

.url-tag.invalid {
  border-color: color-mix(in srgb, var(--danger) 45%, transparent);
  background: var(--danger-soft);
}

.platform-icon { font-size: 16px; line-height: 1; }

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
  border-radius: 5px;
  background: var(--bg-card);
}

.url-text {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 12.5px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tag-btn {
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  border-radius: var(--radius-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: var(--text-tertiary);
}

.tag-btn.parse:hover { background: var(--accent-soft); color: var(--accent); }
.tag-btn.remove:hover { background: var(--danger-soft); color: var(--danger); }

.action-buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.parse-all { flex: 1; min-width: 150px; }

@media (max-width: 768px) {
  .action-buttons { flex-direction: column; }
  .action-buttons button { width: 100%; }
}
</style>
