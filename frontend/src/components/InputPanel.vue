<template>
  <div class="search-panel">
    <form class="search-bar" :class="{ focused: isFocused, invalid: query && !isValid }" @submit.prevent="submit">
      <span class="search-icon"><Icon name="link" :size="20" /></span>
      <input
        ref="inputEl"
        v-model="query"
        type="text"
        class="search-input"
        placeholder="粘贴视频链接，回车解析…"
        spellcheck="false"
        autocomplete="off"
        @focus="isFocused = true"
        @blur="isFocused = false"
        @keydown.enter.prevent="submit"
      />
      <button
        v-if="query"
        type="button"
        class="clear-btn"
        title="清空"
        @click="clearQuery"
      >
        <Icon name="close" :size="16" />
      </button>
      <button type="submit" class="search-go" :disabled="!isValid || isParsing">
        <Icon v-if="!isParsing" name="search" :size="18" />
        <span v-else class="spinner"></span>
        <span class="go-label">{{ isParsing ? '解析中' : '解析' }}</span>
      </button>
    </form>

    <div class="search-tools">
      <button class="tool-chip" @click="pasteFromClipboard">
        <Icon name="clipboard" :size="14" /> 粘贴链接
      </button>
      <span v-if="query && !isValid" class="tool-warn">
        <Icon name="alert" :size="14" /> 链接格式无效
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { isValidUrl } from '../utils/platform'
import { api } from '../api'
import { useAppStore } from '../stores/app'
import Icon from './Icon.vue'

const VIP_HINT_HOSTS = ['bilibili.com', 'b23.tv', 'v.qq.com', 'm.v.qq.com', 'iqiyi.com', 'iq.com', 'youku.com', 'mgtv.com', 'tudou.com', 'tv.sohu.com', 'film.sohu.com', 'le.com', 'pptv.com', 'wasu.cn', 'acfun.cn', '1905.com']

const store = useAppStore()
const query = ref('')
const isFocused = ref(false)
const isParsing = ref(false)
const inputEl = ref(null)

const emit = defineEmits(['parse-success'])

const isValid = computed(() => isValidUrl(query.value.trim()))

onMounted(() => {
  inputEl.value?.focus()
})

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
  if (res.code !== 0) {
    throw new Error(res.msg || res.detail || '未知错误')
  }
  store.setVideoInfo(res.data)
  emit('parse-success', res.data)
}

async function submit() {
  const url = query.value.trim()
  if (!isValidUrl(url) || isParsing.value) return

  isParsing.value = true
  store.setParsing(true)
  try {
    try {
      const res = await api.parseInfo(url)
      applyParseResult(res)
    } catch (err) {
      if (!mightNeedVipFallback(url)) throw err
      const vipRes = await api.parseInfo(url, { forceVip: true })
      applyParseResult(vipRes)
    }
  } catch (err) {
    alert('解析失败：' + toFriendlyParseError(err))
  } finally {
    isParsing.value = false
    store.setParsing(false)
  }
}

function clearQuery() {
  query.value = ''
  inputEl.value?.focus()
}

async function pasteFromClipboard() {
  try {
    const text = await navigator.clipboard.readText()
    if (text) {
      query.value = text.trim().split('\n')[0].trim()
      inputEl.value?.focus()
      if (isValid.value) submit()
    }
  } catch {
    alert('无法访问剪贴板，请手动粘贴')
  }
}
</script>

<style scoped>
.search-panel {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.search-bar {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 8px 8px 18px;
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-md);
  transition: box-shadow 0.25s var(--ease), border-color 0.25s var(--ease),
              transform 0.25s var(--ease-out);
}

.search-bar.focused {
  border-color: var(--accent);
  box-shadow: 0 0 0 4px var(--accent-ring), var(--shadow-lg);
  transform: translateY(-1px);
}

.search-bar.invalid {
  border-color: color-mix(in srgb, var(--danger) 50%, transparent);
}

.search-icon {
  display: flex;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.search-bar.focused .search-icon { color: var(--accent); }

.search-input {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  padding: 12px 0;
  font-size: 16px;
  color: var(--text-primary);
  box-shadow: none;
}

.search-input:focus { box-shadow: none; }

.clear-btn {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: var(--radius-pill);
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: var(--text-tertiary);
}

.clear-btn:hover { background: var(--bg-hover); color: var(--text-primary); }

.search-go {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 46px;
  padding: 0 22px;
  border-radius: var(--radius-pill);
  background: var(--accent);
  color: var(--text-on-brand);
  font-size: 15px;
  font-weight: 600;
  box-shadow: var(--shadow-xs);
}

.search-go:hover:not(:disabled) {
  background: var(--accent-hover);
  box-shadow: 0 4px 16px var(--accent-ring);
}

.search-go:active:not(:disabled) { transform: scale(0.97); }

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.search-tools {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 24px;
}

.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--bg-card) 70%, transparent);
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  backdrop-filter: blur(8px);
}

.tool-chip:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}

.tool-warn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: var(--danger);
}

@media (max-width: 640px) {
  .go-label { display: none; }
  .search-go { padding: 0 16px; }
  .search-input { font-size: 15px; }
}
</style>
