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
  max-width: 880px;
  margin: 0 auto;
  padding: 0 24px 64px;
  display: flex;
  flex-direction: column;
}

.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 22px;
  padding-top: clamp(80px, 18vh, 200px);
  transition: padding-top 0.55s var(--ease-out), gap 0.45s var(--ease-out);
}

.hero.compact {
  padding-top: 28px;
  gap: 18px;
}

.hero-brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.hero-logo { width: 46px; height: 46px; }

.hero-title {
  font-size: clamp(28px, 4.6vw, 44px);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.05;
  margin: 0;
  color: var(--text-primary);
}

.hero.compact .hero-title { font-size: clamp(22px, 3vw, 28px); }
.hero.compact .hero-logo { width: 36px; height: 36px; }

.t-accent {
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.t-muted { color: var(--text-tertiary); font-weight: 700; }

.hero-tagline {
  font-size: 16px;
  color: var(--text-secondary);
  margin: -6px 0 4px;
}

.search-wrap {
  width: 100%;
  max-width: 720px;
}

.result-area { margin-top: 36px; }

.result-enter-active {
  transition: opacity 0.5s var(--ease-out), transform 0.5s var(--ease-out);
}
.result-leave-active {
  transition: opacity 0.3s var(--ease), transform 0.3s var(--ease);
}
.result-enter-from { opacity: 0; transform: translateY(24px); }
.result-leave-to { opacity: 0; transform: translateY(12px); }

@media (max-width: 768px) {
  .main-content { padding: 0 16px 48px; }
  .hero { padding-top: clamp(48px, 12vh, 120px); }
  .hero-tagline { font-size: 14px; }
  .result-area { margin-top: 24px; }
}
</style>
