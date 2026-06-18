<template>
  <div class="video-logo" aria-hidden="true">
    <img src="/vdio-logo.png" alt="" class="logo-image" />
  </div>
</template>

<script setup>
</script>

<style scoped>
.video-logo {
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 11px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-xs);
  overflow: hidden;
}

.logo-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
  transform: scale(1.16);
}
</style>
