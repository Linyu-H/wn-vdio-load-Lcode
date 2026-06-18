<template>
  <div class="preview-panel card">
    <div v-if="!videoInfo" class="empty-state">
      <div class="empty-icon">🎬</div>
      <p class="empty-text">解析后将在此处预览视频信息</p>
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
          <div>
            <div class="site-name">{{ videoInfo.platform_name }}</div>
            <a class="source-link" :href="videoInfo.url" target="_blank" rel="noopener noreferrer">
              打开原视频页
            </a>
          </div>
        </div>
        <span v-if="videoInfo.playlist_count > 0" class="playlist-badge">
          📋 {{ videoInfo.playlist_count }} 个视频
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

      <div class="info-content">
        <h3 class="video-title">{{ videoInfo.title }}</h3>
        <div class="meta-info">
          <span v-if="videoInfo.uploader" class="meta-item">
            👤 {{ videoInfo.uploader }}
          </span>
          <span v-if="videoInfo.duration" class="meta-item">
            ⏱️ {{ formatDuration(videoInfo.duration) }}
          </span>
          <span class="meta-item">
            {{ getPlatformIcon(videoInfo.platform) }} {{ videoInfo.platform_name }}
          </span>
        </div>
      </div>

      <div v-if="videoInfo.vip_supported && videoInfo.vip_parse_sources?.length" class="vip-selector">
        <h4>VIP 解析源</h4>
        <div class="vip-buttons">
          <button
            v-for="source in videoInfo.vip_parse_sources"
            :key="source.id"
            @click="selectedVipSource = source.id"
            class="quality-btn"
            :class="{ active: selectedVipSource === source.id }"
          >
            {{ source.name }}
          </button>
        </div>
        <p class="vip-tip">预览使用当前解析源；下载仅在点击下载后尝试使用当前解析源直链。</p>
      </div>

      <div class="quality-selector">
        <h4>选择画质</h4>
        <div class="quality-buttons">
          <button
            v-for="q in videoInfo.qualities"
            :key="q.id"
            @click="selectedQuality = q.id"
            class="quality-btn"
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
          {{ downloading ? '下载中...' : (videoInfo.vip_supported ? '📥 尝试 VIP 下载' : '📥 下载视频') }}
        </button>
        <button
          @click="startDownload(true)"
          class="btn-secondary download-btn"
          :disabled="downloading"
        >
          🎵 仅下载音频
        </button>
      </div>

      <div v-if="taskStatus" class="progress-section">
        <div class="progress-header">
          <span class="status-text">{{ taskStatus.status }}</span>
          <span class="progress-percent">{{ taskStatus.progress }}%</span>
        </div>
        <div class="progress-bar">
          <div
            class="progress-fill"
            :style="{ width: taskStatus.progress + '%' }"
          ></div>
        </div>
        <div v-if="taskStatus.speed" class="progress-meta">
          <span>速度: {{ taskStatus.speed }}</span>
          <span v-if="taskStatus.eta">剩余: {{ taskStatus.eta }}s</span>
        </div>
        <div v-if="taskStatus.status === 'completed'" class="download-link">
          <a :href="getDownloadUrl(taskStatus.id)" class="btn-primary" download>
            💾 保存到本地
          </a>
        </div>
        <div v-if="taskStatus.error" class="error-message">
          ❌ {{ taskStatus.error }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { getPlatformIcon } from '../utils/platform'

const store = useAppStore()
const videoInfo = computed(() => store.videoInfo)
const selectedQuality = ref('1080')
const selectedVipSource = ref(null)
const siteLogoBroken = ref(false)
const downloading = ref(false)
const taskStatus = ref(null)
let ws = null

const currentPreviewUrl = computed(() => {
  if (!videoInfo.value) return ''
  if (videoInfo.value.vip_supported && selectedVipSource.value) {
    const source = videoInfo.value.vip_parse_sources?.find(item => item.id === selectedVipSource.value)
    if (source) {
      return source.preview_url || (source.url + encodeURIComponent(videoInfo.value.url))
    }
  }
  return videoInfo.value.vip_preview_url || videoInfo.value.preview_url || ''
})

watch(videoInfo, (newInfo) => {
  siteLogoBroken.value = false
  if (newInfo?.vip_supported && newInfo.vip_parse_sources?.length) {
    selectedVipSource.value = newInfo.vip_parse_sources[0].id
  } else {
    selectedVipSource.value = null
  }
  if (newInfo && newInfo.qualities && newInfo.qualities.length > 0) {
    selectedQuality.value = newInfo.qualities.find(q => q.id === '1080')?.id || newInfo.qualities[0].id
  }
})

function formatDuration(seconds) {
  if (!seconds) return '未知'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  return `${m}:${s.toString().padStart(2, '0')}`
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
  gap: 16px;
  opacity: 0.5;
}

.empty-icon {
  font-size: 64px;
}

.empty-text {
  font-size: 16px;
  color: var(--text-secondary);
}

.video-info {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.site-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
}

.site-brand {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.site-logo,
.site-logo-fallback {
  width: 48px;
  height: 48px;
  flex: 0 0 auto;
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.site-logo {
  object-fit: cover;
  padding: 3px;
}

.vip-selector h4 {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 12px 0;
}

.vip-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.vip-tip {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.site-logo-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.site-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.source-link {
  display: inline-block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--accent-primary);
  text-decoration: none;
}

.source-link:hover {
  text-decoration: underline;
}

.iframe-preview,
.thumbnail {
  width: 100%;
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
}

.iframe-preview {
  aspect-ratio: 16 / 9;
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
  gap: 12px;
}

.video-title {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  margin: 0;
}

.meta-info {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.playlist-badge {
  flex: 0 0 auto;
  background: var(--accent-primary);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.quality-selector h4 {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 12px 0;
}

.quality-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.quality-btn {
  padding: 10px 16px;
  background: var(--bg-primary);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.quality-btn:hover {
  border-color: var(--accent-primary);
  transform: translateY(-2px);
}

.quality-btn.active {
  background: var(--accent-gradient);
  color: white;
  border-color: var(--accent-primary);
}

.download-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.download-btn {
  flex: 1;
  min-width: 150px;
}

.progress-section {
  padding: 16px;
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 500;
}

.status-text {
  color: var(--accent-primary);
}

.progress-bar {
  height: 8px;
  background: var(--bg-card);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent-gradient);
  transition: width 0.3s ease;
  position: relative;
  overflow: hidden;
}

.progress-fill::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    transparent
  );
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.progress-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
}

.download-link {
  margin-top: 8px;
}

.download-link a {
  display: inline-block;
  text-decoration: none;
  width: 100%;
  text-align: center;
}

.error-message {
  color: #ff6b6b;
  font-size: 14px;
  padding: 12px;
  background: rgba(255, 107, 107, 0.1);
  border-radius: var(--radius-sm);
  border-left: 3px solid #ff6b6b;
}

@media (max-width: 768px) {
  .site-header,
  .download-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .download-btn {
    width: 100%;
  }
}
</style>
