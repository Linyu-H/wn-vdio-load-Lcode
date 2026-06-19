<script setup>
import { computed } from 'vue'
import InputPanel from '../components/InputPanel.vue'
import PreviewPanel from '../components/PreviewPanel.vue'
import VideoLogo from '../components/VideoLogo.vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const hasResult = computed(() => !!store.videoInfo)
</script>

<template>
  <main class="main-content">
    <section class="hero" :class="{ compact: hasResult }">
      <div v-if="!hasResult" class="hero-badge">
        <span class="badge-dot"></span> 全平台 · 秒级解析 · 最高 4K
      </div>
      <div class="hero-brand">
        <VideoLogo class="hero-logo" />
        <h1 class="hero-title">
          <span class="t-accent">analyze</span> vdio loader
          <span class="t-muted">Lcode</span>
        </h1>
      </div>
      <p v-if="!hasResult" class="hero-tagline">粘贴任意视频链接，秒级解析、在线预览、一键下载</p>

      <div class="search-wrap">
        <InputPanel />
      </div>

      <div v-if="!hasResult" class="hero-platforms">
        <span class="hp-label">已支持</span>
        <span class="hp-chip">YouTube</span>
        <span class="hp-chip">哔哩哔哩</span>
        <span class="hp-chip">抖音</span>
        <span class="hp-chip">TikTok</span>
        <span class="hp-chip">X</span>
        <span class="hp-chip">Instagram</span>
        <span class="hp-chip">+1000</span>
      </div>
    </section>

    <transition name="result">
      <section v-if="hasResult" class="result-area">
        <PreviewPanel />
      </section>
    </transition>
  </main>
</template>

<style scoped>
.main-content {
  flex: 1;
  width: 100%;
  max-width: 920px;
  margin: 0 auto;
  padding: 0 24px 80px;
  display: flex;
  flex-direction: column;
}

.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 24px;
  padding-top: clamp(72px, 16vh, 180px);
  transition: padding-top 0.55s var(--ease-out), gap 0.45s var(--ease-out);
}

.hero.compact {
  padding-top: 28px;
  gap: 18px;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 15px 6px 12px;
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--text-secondary);
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-pill);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  box-shadow: var(--shadow-sm);
  animation: rise 0.7s var(--ease-out) both;
}
.badge-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 0 rgba(34,197,94,0.5);
  animation: pulse-dot 2s var(--ease) infinite;
}
@keyframes pulse-dot {
  0% { box-shadow: 0 0 0 0 rgba(34,197,94,0.5); }
  70% { box-shadow: 0 0 0 8px rgba(34,197,94,0); }
  100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
}

.hero-brand {
  display: flex;
  align-items: center;
  gap: 16px;
  animation: rise 0.7s var(--ease-out) 0.06s both;
}

.hero-logo {
  width: 56px; height: 56px;
  filter: drop-shadow(0 6px 18px var(--accent-ring));
}

.hero-title {
  font-size: clamp(34px, 6vw, 60px);
  font-weight: 800;
  letter-spacing: -0.035em;
  line-height: 1.02;
  margin: 0;
  color: var(--text-primary);
  text-shadow: 0 1px 30px var(--accent-ring);
}

.hero.compact .hero-title { font-size: clamp(22px, 3vw, 30px); }
.hero.compact .hero-logo { width: 38px; height: 38px; }

.t-accent {
  background: var(--accent-flow);
  background-size: 280% auto;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: hue-flow 6s linear infinite;
}
@keyframes hue-flow {
  to { background-position: 280% center; }
}

.t-muted { color: var(--text-tertiary); font-weight: 700; }

.hero-tagline {
  font-size: 17px;
  color: var(--text-secondary);
  margin: -8px 0 2px;
  animation: rise 0.7s var(--ease-out) 0.12s both;
}

.search-wrap {
  width: 100%;
  max-width: 720px;
  animation: rise 0.7s var(--ease-out) 0.18s both;
}

.hero-platforms {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
  animation: rise 0.7s var(--ease-out) 0.26s both;
}
.hp-label { font-size: 12.5px; color: var(--text-tertiary); margin-right: 2px; }
.hp-chip {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 5px 12px;
  border-radius: var(--radius-pill);
  background: color-mix(in srgb, var(--bg-card) 55%, transparent);
  border: 1px solid var(--border);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  transition: transform var(--dur) var(--ease-spring), color var(--dur) var(--ease), border-color var(--dur) var(--ease);
}
.hp-chip:hover {
  transform: translateY(-2px);
  color: var(--accent);
  border-color: var(--accent);
}

@keyframes rise {
  from { opacity: 0; transform: translateY(18px); }
  to { opacity: 1; transform: translateY(0); }
}

.result-area { margin-top: 40px; }

.result-enter-active {
  transition: opacity 0.5s var(--ease-out), transform 0.5s var(--ease-out);
}
.result-leave-active {
  transition: opacity 0.3s var(--ease), transform 0.3s var(--ease);
}
.result-enter-from { opacity: 0; transform: translateY(28px) scale(0.99); }
.result-leave-to { opacity: 0; transform: translateY(12px); }

@media (max-width: 768px) {
  .main-content { padding: 0 16px 48px; }
  .hero { padding-top: clamp(40px, 10vh, 100px); }
  .hero-tagline { font-size: 14px; }
  .result-area { margin-top: 24px; }
}

@media (prefers-reduced-motion: reduce) {
  .t-accent { animation: none; }
  .hero-badge, .hero-brand, .hero-tagline, .search-wrap, .hero-platforms { animation: none; }
}
</style>
