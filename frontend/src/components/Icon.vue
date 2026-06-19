<template>
  <svg
    class="icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="(d, i) in paths" :key="i" :d="d" />
    <template v-for="(c, i) in circles" :key="'c' + i">
      <circle :cx="c.cx" :cy="c.cy" :r="c.r" />
    </template>
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 18 },
  strokeWidth: { type: [Number, String], default: 1.75 },
})

// 线性图标库（stroke-based，24x24 网格）
const ICONS = {
  download: { p: ['M12 3v12', 'M7 10l5 5 5-5', 'M4 18v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1'] },
  audio: { p: ['M9 18V6l10-2v12'], c: [{ cx: 6, cy: 18, r: 3 }, { cx: 16, cy: 16, r: 3 }] },
  search: { p: ['M21 21l-4.3-4.3'], c: [{ cx: 11, cy: 11, r: 7 }] },
  history: { p: ['M3 3v5h5', 'M3.05 13A9 9 0 1 0 6 5.3L3 8', 'M12 7v5l3 2'] },
  clipboard: { p: ['M9 4h6a1 1 0 0 1 1 1v1H8V5a1 1 0 0 1 1-1z', 'M8 6H6a1 1 0 0 0-1 1v13a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1h-2'] },
  trash: { p: ['M3 6h18', 'M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2', 'M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6', 'M10 11v6', 'M14 11v6'] },
  refresh: { p: ['M21 12a9 9 0 1 1-2.64-6.36', 'M21 3v5h-5'] },
  close: { p: ['M18 6 6 18', 'M6 6l12 12'] },
  sun: { p: ['M12 2v2', 'M12 20v2', 'M4.9 4.9l1.4 1.4', 'M17.7 17.7l1.4 1.4', 'M2 12h2', 'M20 12h2', 'M4.9 19.1l1.4-1.4', 'M17.7 6.3l1.4-1.4'], c: [{ cx: 12, cy: 12, r: 4 }] },
  moon: { p: ['M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z'] },
  eye: { p: ['M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z'], c: [{ cx: 12, cy: 12, r: 3 }] },
  link: { p: ['M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1', 'M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1'] },
  play: { p: ['M7 4v16l13-8z'] },
  film: { p: ['M3 4h18v16H3z', 'M7 4v16', 'M17 4v16', 'M3 9h4', 'M17 9h4', 'M3 15h4', 'M17 15h4'] },
  user: { p: ['M20 21v-1a6 6 0 0 0-12 0v1'], c: [{ cx: 12, cy: 7, r: 4 }] },
  clock: { p: ['M12 7v5l3 2'], c: [{ cx: 12, cy: 12, r: 9 }] },
  layers: { p: ['M12 3 2 8l10 5 10-5-10-5z', 'M2 13l10 5 10-5', 'M2 18l10 5 10-5'] },
  check: { p: ['M20 6 9 17l-5-5'] },
  alert: { p: ['M12 8v5', 'M12 16.5v.5'], c: [{ cx: 12, cy: 12, r: 9 }] },
  bolt: { p: ['M13 2 4 14h7l-1 8 9-12h-7l1-8z'] },
  external: { p: ['M15 3h6v6', 'M10 14 21 3', 'M19 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5'] },
  save: { p: ['M5 3h11l3 3v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z', 'M8 3v5h7', 'M8 21v-7h8v7'] },
  shield: { p: ['M12 3l8 3v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6l8-3z', 'M9 12l2 2 4-4'] },
}

const def = computed(() => ICONS[props.name] || { p: [] })
const paths = computed(() => def.value.p || [])
const circles = computed(() => def.value.c || [])
</script>

<style scoped>
.icon {
  display: inline-block;
  flex-shrink: 0;
  vertical-align: middle;
}
</style>
