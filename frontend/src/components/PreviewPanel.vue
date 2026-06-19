<template>
  <div class="preview-panel card">
    <div v-if="!videoInfo" class="empty-state">
      <div class="empty-icon"><Icon name="film" :size="30" :stroke-width="1.5" /></div>
      <p class="empty-text">解析后将在此处预览视频</p>
      <p class="empty-sub">粘贴链接并点击「解析全部」开始</p>
    </div>

    <div v-else class="video-info">
      <div class="site-header">
        <div class="site-brand">
          <img
            v-if="videoInfo.site_logo && !siteLogoBroken"
            :src="videoInfo.site_logo"
            :alt="`${videoInfo.platform_name} logo`"
            class="site-logo"
            @error="hideBrokenLogo"
          />
          <span v-else class="site-logo-fallback">
            {{ getPlatformIcon(videoInfo.platform) }}
          </span>
          <div class="site-meta">
            <div class="site-name">{{ videoInfo.platform_name }}</div>
            <a class="source-link" :href="videoInfo.url" target="_blank" rel="noopener noreferrer">
              打开原视频页 <Icon name="external" :size="12" />
            </a>
          </div>
        </div>
        <span v-if="videoInfo.vip_supported" class="vip-badge">
          <Icon name="bolt" :size="13" /> VIP 解析
        </span>
        <span v-if="videoInfo.playlist_count > 0" class="playlist-badge">
          <Icon name="layers" :size="13" /> {{ videoInfo.playlist_count }}
        </span>
      </div>

      <div v-if="currentPreviewUrl" class="iframe-preview">
        <iframe
          :src="currentPreviewUrl"
          :title="`预览 ${videoInfo.title}`"
          loading="lazy"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; fullscreen; gyroscope; picture-in-picture; web-share"
          allowfullscreen
          referrerpolicy="strict-origin-when-cross-origin"
        ></iframe>
      </div>
      <div v-else-if="videoInfo.thumbnail" class="thumbnail">
        <img :src="videoInfo.thumbnail" :alt="videoInfo.title" loading="lazy" />
      </div>

      <div v-if="hasEpisodes" class="episode-bar">
        <button class="ep-btn" :disabled="!hasPrev" @click="prevEpisode" title="上一集">
          <Icon name="play" :size="14" :stroke-width="2" style="transform: rotate(180deg)" /> 上一集
        </button>
        <span class="ep-current" :title="currentEpisodeTitle">
          {{ episodeIndex + 1 }} / {{ episodes.length }}
          <em v-if="currentEpisodeTitle">· {{ currentEpisodeTitle }}</em>
        </span>
        <button class="ep-btn" :disabled="!hasNext" @click="nextEpisode" title="下一集">
          下一集 <Icon name="play" :size="14" :stroke-width="2" />
        </button>
      </div>

      <div v-if="videoInfo.vip_supported" class="auto-line">
        <span v-if="resolving" class="line-state">
          <span class="mini-spinner"></span> 正在为你自动匹配线路…
        </span>
        <span v-else class="line-state ok">
          <Icon name="bolt" :size="13" /> 自动线路 · {{ currentSourceName || '默认' }}
        </span>
        <button class="switch-src" @click="reportAndSwitch" :disabled="resolving" title="当前画面播不出？禁用并自动换下一条">
          <Icon name="refresh" :size="13" /> 播不出？换线路
        </button>
      </div>

      <div class="info-content">
        <h3 class="video-title">{{ videoInfo.title }}</h3>
        <div class="meta-info">
          <span v-if="videoInfo.uploader" class="meta-item">
            <Icon name="user" :size="14" /> {{ videoInfo.uploader }}
          </span>
          <span v-if="videoInfo.duration" class="meta-item">
            <Icon name="clock" :size="14" /> {{ formatDuration(videoInfo.duration) }}
          </span>
        </div>
      </div>

      <div class="selector-group">
        <span class="section-label">画质</span>
        <div class="chip-row">
          <button
            v-for="q in videoInfo.qualities"
            :key="q.id"
            @click="selectedQuality = q.id"
            class="chip"
            :class="{ active: selectedQuality === q.id }"
          >
            {{ q.label }}
          </button>
        </div>
      </div>

      <div class="download-actions">
        <button
          @click="startDownload(false)"
          class="btn-primary download-btn"
          :disabled="downloading"
        >
          <Icon name="download" :size="16" />
          {{ downloading ? '下载中…' : (videoInfo.vip_supported ? 'VIP 下载' : '下载视频') }}
        </button>
        <button
          @click="startDownload(true)"
          class="btn-secondary download-btn audio"
          :disabled="downloading"
        >
          <Icon name="audio" :size="16" />
          仅音频
        </button>
      </div>

      <div v-if="taskStatus" class="progress-section">
        <div class="progress-header">
          <span class="status-text">
            <span class="status-dot" :class="taskStatus.status"></span>
            {{ statusLabel(taskStatus.status) }}
          </span>
          <span class="progress-percent">{{ taskStatus.progress }}%</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: taskStatus.progress + '%' }"></div>
        </div>
        <div v-if="taskStatus.speed" class="progress-meta">
          <span>{{ taskStatus.speed }}</span>
          <span v-if="taskStatus.eta">剩余 {{ taskStatus.eta }}s</span>
        </div>
        <div v-if="taskStatus.status === 'completed'" class="download-link">
          <a :href="getDownloadUrl(taskStatus.id)" class="btn-primary" download>
            <Icon name="save" :size="16" /> 保存到本地
          </a>
        </div>
        <div v-if="taskStatus.error" class="error-message">
          <Icon name="alert" :size="15" /> {{ taskStatus.error }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { getPlatformIcon } from '../utils/platform'
import Icon from './Icon.vue'

const store = useAppStore()
const videoInfo = computed(() => store.videoInfo)
const selectedQuality = ref('1080')
const selectedVipSource = ref(null)
const siteLogoBroken = ref(false)
const downloading = ref(false)
const taskStatus = ref(null)
let ws = null

// 自动解析 / 健康源
const rankedSources = ref([])      // 后端探测排序后的源（健康在前）
const resolving = ref(false)       // 正在探测健康源
const autoMode = ref(true)         // 自动模式：用健康源自动播放
let switchTimer = null

// 上下集
const episodes = ref([])
const episodeIndex = ref(-1)
const hasEpisodes = computed(() => episodes.value.length > 1)
const hasPrev = computed(() => episodeIndex.value > 0)
const hasNext = computed(() => episodeIndex.value >= 0 && episodeIndex.value < episodes.value.length - 1)
const currentEpisodeTitle = computed(() =>
  episodeIndex.value >= 0 ? episodes.value[episodeIndex.value]?.title : ''
)

// 当前用于预览的源列表：优先后端探测结果，否则回退原始顺序
const displaySources = computed(() => {
  if (rankedSources.value.length) return rankedSources.value
  return videoInfo.value?.vip_parse_sources || []
})

const currentPreviewUrl = computed(() => {
  if (!videoInfo.value) return ''
  if (videoInfo.value.vip_supported && selectedVipSource.value) {
    const source = displaySources.value.find(item => item.id === selectedVipSource.value)
    if (source) {
      return source.preview_url || (source.url + encodeURIComponent(videoInfo.value.url))
    }
  }
  return videoInfo.value.vip_preview_url || videoInfo.value.preview_url || ''
})

const currentSourceHealthy = computed(() => {
  const s = rankedSources.value.find(item => item.id === selectedVipSource.value)
  return s ? s.healthy : null
})

const currentSourceName = computed(() => {
  const s = displaySources.value.find(item => item.id === selectedVipSource.value)
  return s ? s.name : ''
})

watch(videoInfo, (newInfo) => {
  siteLogoBroken.value = false
  rankedSources.value = []
  if (newInfo && newInfo.qualities && newInfo.qualities.length > 0) {
    selectedQuality.value = newInfo.qualities.find(q => q.id === '1080')?.id || newInfo.qualities[0].id
  }
  if (newInfo?.vip_supported && newInfo.vip_parse_sources?.length) {
    selectedVipSource.value = newInfo.vip_parse_sources[0].id
    resolveHealthySources(newInfo.url)   // VIP：自动探测健康源
  } else {
    selectedVipSource.value = null
  }
  if (newInfo?.url) loadEpisodes(newInfo.url)
})

async function resolveHealthySources(url) {
  resolving.value = true
  try {
    const res = await api.resolveVip(url)
    if (res.code === 0 && res.data.sources?.length) {
      rankedSources.value = res.data.sources
      if (autoMode.value && res.data.best) {
        selectedVipSource.value = res.data.best.id   // 自动切到最佳健康源
      }
    }
  } catch { /* 探测失败保持原选择 */ } finally {
    resolving.value = false
  }
}

async function loadEpisodes(url) {
  episodes.value = []
  episodeIndex.value = -1
  try {
    const res = await api.getEpisodes(url)
    if (res.code === 0 && res.data.episodes?.length > 1) {
      episodes.value = res.data.episodes
      episodeIndex.value = res.data.current_index
    }
  } catch { /* 无上下集 */ }
}

async function gotoEpisode(idx) {
  if (idx < 0 || idx >= episodes.value.length) return
  const ep = episodes.value[idx]
  try {
    const res = await api.parseInfo(ep.url)
    if (res.code === 0) {
      store.setVideoInfo(res.data)   // 触发 watch，自动重新探测+加载剧集
    } else {
      // 普通视频解析失败，尝试 VIP
      const vip = await api.parseInfo(ep.url, { forceVip: true })
      if (vip.code === 0) store.setVideoInfo(vip.data)
    }
  } catch (err) {
    alert('切换剧集失败：' + (err.message || ''))
  }
}

function prevEpisode() { if (hasPrev.value) gotoEpisode(episodeIndex.value - 1) }
function nextEpisode() { if (hasNext.value) gotoEpisode(episodeIndex.value + 1) }

// 手动选源（已隐藏列表，保留以兼容）
function selectSource(id) {
  selectedVipSource.value = id
  autoMode.value = false
}

// 用户反馈当前源播不了：禁用该源（后端熔断，以后不再用）+ 本地移除并切下一个
async function reportAndSwitch() {
  const cur = selectedVipSource.value
  const list = displaySources.value
  const curIdx = list.findIndex(s => s.id === cur)

  if (cur) {
    await api.reportVipFailure(cur)   // 后端将该源 enabled=false
    // 本地把这个源剔除，避免再被选中
    rankedSources.value = (rankedSources.value.length ? rankedSources.value : list)
      .filter(s => s.id !== cur)
    if (videoInfo.value?.vip_parse_sources) {
      videoInfo.value.vip_parse_sources = videoInfo.value.vip_parse_sources.filter(s => s.id !== cur)
    }
  }

  const remaining = displaySources.value
  const next = remaining[curIdx] || remaining[0]   // 剔除后，原 curIdx 即下一个
  if (next) {
    selectedVipSource.value = next.id
  } else {
    selectedVipSource.value = null
    alert('已尝试所有解析源，建议稍后重试或在管理端添加新源')
  }
}

onBeforeUnmount(() => {
  if (switchTimer) clearTimeout(switchTimer)
  if (ws) ws.close()
})

function formatDuration(seconds) {
  if (!seconds) return '未知'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  return `${m}:${s.toString().padStart(2, '0')}`
}

const STATUS_LABELS = {
  waiting: '等待中',
  downloading: '下载中',
  processing: '处理中',
  completed: '已完成',
  error: '失败',
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status
}

function hideBrokenLogo() {
  siteLogoBroken.value = true
}

async function startDownload(audioOnly) {
  if (!videoInfo.value || downloading.value) return

  downloading.value = true
  taskStatus.value = null

  try {
    const res = await api.createDownload(
      videoInfo.value.url,
      audioOnly ? 'audio' : selectedQuality.value,
      audioOnly,
      selectedVipSource.value
    )

    if (res.code === 0) {
      const taskId = res.data.task_id
      connectWebSocket(taskId)
    } else {
      alert('创建下载任务失败：' + (res.msg || res.detail))
      downloading.value = false
    }
  } catch (err) {
    alert('创建下载任务失败：' + err.message)
    downloading.value = false
  }
}

function connectWebSocket(taskId) {
  ws = new WebSocket(api.getWsUrl(taskId))

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    if (msg.code === 0 && msg.data) {
      taskStatus.value = msg.data

      if (msg.data.status === 'completed') {
        downloading.value = false
        store.addHistory({
          id: taskId,
          title: videoInfo.value.title,
          thumbnail: videoInfo.value.thumbnail,
          platform: videoInfo.value.platform,
          url: videoInfo.value.url,
          created_at: Date.now()
        })
        ws.close()
      } else if (msg.data.status === 'error') {
        downloading.value = false
        ws.close()
      }
    }
  }

  ws.onerror = () => {
    downloading.value = false
    alert('WebSocket 连接失败')
  }

  ws.onclose = () => {
    downloading.value = false
  }
}

function getDownloadUrl(taskId) {
  return api.getFileUrl(taskId)
}
</script>

<style scoped>
.preview-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 380px;
}

.empty-icon {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.empty-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary);
}

.empty-sub {
  font-size: 13px;
  color: var(--text-tertiary);
}

.video-info {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.video-info > * {
  animation: rise 0.5s var(--ease-out) both;
}
.video-info > *:nth-child(1) { animation-delay: 0.02s; }
.video-info > *:nth-child(2) { animation-delay: 0.08s; }
.video-info > *:nth-child(3) { animation-delay: 0.14s; }
.video-info > *:nth-child(4) { animation-delay: 0.20s; }
.video-info > *:nth-child(5) { animation-delay: 0.26s; }
.video-info > *:nth-child(6) { animation-delay: 0.32s; }

@keyframes rise {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.site-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.site-brand {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.site-logo,
.site-logo-fallback {
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  border-radius: 11px;
  background: var(--bg-card);
  border: 1px solid var(--border);
}

.site-logo {
  object-fit: cover;
  padding: 3px;
}

.site-logo-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.site-meta { min-width: 0; }

.site-name {
  font-size: 14.5px;
  font-weight: 700;
  color: var(--text-primary);
}

.source-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 1px;
  font-size: 12px;
  font-weight: 500;
  color: var(--accent);
  text-decoration: none;
}

.source-link:hover { text-decoration: underline; }

.vip-badge,
.playlist-badge {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 600;
}

.vip-badge {
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid color-mix(in srgb, var(--accent) 25%, transparent);
}

.playlist-badge {
  background: var(--bg-inset);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.iframe-preview,
.thumbnail {
  width: 100%;
  border-radius: var(--radius);
  overflow: hidden;
  background: #000;
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-lg), 0 0 0 1px rgba(37,99,235,0.06);
}

.iframe-preview { aspect-ratio: 16 / 9; position: relative; }
.iframe-preview::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  box-shadow: inset 0 0 80px rgba(0,0,0,0.35);
  pointer-events: none;
}

.iframe-preview iframe {
  width: 100%;
  height: 100%;
  display: block;
  border: 0;
}

.thumbnail img {
  width: 100%;
  height: auto;
  display: block;
}

.info-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.video-title {
  font-size: 17px;
  font-weight: 700;
  line-height: 1.4;
  letter-spacing: -0.01em;
  margin: 0;
}

.meta-info {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: var(--text-secondary);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.meta-item :deep(.icon) { color: var(--text-tertiary); }

.selector-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chip-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chip {
  padding: 8px 15px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  transition: background var(--dur) var(--ease), border-color var(--dur) var(--ease),
              color var(--dur) var(--ease), transform var(--dur) var(--ease-spring);
}

.chip:hover {
  border-color: var(--border-strong);
  color: var(--text-primary);
  transform: translateY(-2px);
}

.chip:active { transform: translateY(0); }

/* ── 上下集导航 ── */
.episode-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.ep-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}
.ep-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.ep-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.ep-current {
  flex: 1;
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ep-current em { font-style: normal; color: var(--text-tertiary); font-weight: 500; }

/* ── 源健康 + 自动选源 ── */
.auto-line {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.line-state {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-tertiary);
}
.line-state.ok { color: var(--accent); }
.switch-src {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-pill);
}
.switch-src:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
.switch-src:disabled { opacity: 0.5; cursor: not-allowed; }

.mini-spinner {
  width: 12px; height: 12px;
  border: 2px solid var(--border-strong);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.chip.active {
  background: var(--accent-gradient);
  color: #fff;
  border-color: transparent;
  box-shadow: var(--glow-accent);
  transform: translateY(-1px);
}

.hint {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-tertiary);
}

.hint :deep(.icon) { margin-top: 1px; flex-shrink: 0; }

.download-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.download-btn {
  flex: 1;
  min-width: 150px;
}

.download-btn.audio { flex: 0 0 auto; min-width: 120px; }

.progress-section {
  padding: 16px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
}

.status-text {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-tertiary);
}

.status-dot.downloading,
.status-dot.processing,
.status-dot.waiting {
  background: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-ring);
  animation: pulse 1.4s var(--ease) infinite;
}

.status-dot.completed { background: var(--brand-500); }
.status-dot.error { background: var(--danger); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.progress-percent {
  font-family: var(--font-mono);
  color: var(--accent);
}

.progress-bar {
  height: 7px;
  background: var(--bg-inset);
  border-radius: var(--radius-pill);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent-gradient);
  border-radius: var(--radius-pill);
  transition: width 0.3s var(--ease);
  position: relative;
  overflow: hidden;
}

.progress-fill::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.35), transparent);
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

.progress-meta {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
}

.download-link { margin-top: 4px; }

.download-link a {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-decoration: none;
  width: 100%;
}

.error-message {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  color: var(--danger);
  font-size: 13px;
  line-height: 1.5;
  padding: 12px 14px;
  background: var(--danger-soft);
  border-radius: var(--radius-sm);
  border: 1px solid color-mix(in srgb, var(--danger) 25%, transparent);
}

.error-message :deep(.icon) { margin-top: 1px; flex-shrink: 0; }

@media (max-width: 768px) {
  .site-header { flex-wrap: wrap; }
  .download-actions { flex-direction: column; }
  .download-btn,
  .download-btn.audio { width: 100%; min-width: 0; }
}
</style>
