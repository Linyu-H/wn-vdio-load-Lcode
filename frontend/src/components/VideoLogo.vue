<template>
  <div class="video-logo" aria-hidden="true">
    <img src="/vdio-logo.png" alt="" class="logo-image" />
  </div>
</template>

<script setup>
</script>

<style scoped>
.video-logo {
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
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
