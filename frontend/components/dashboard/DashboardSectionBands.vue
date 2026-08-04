<template>
  <div class="section-bands" aria-hidden="true">
    <div
      v-for="section in sections"
      v-show="bounds[section.id]"
      :key="section.id"
      class="section-band"
      :style="bandStyle(section)"
    />
  </div>
</template>

<script setup lang="ts">
import type { DashboardSection, SectionBounds } from '~/composables/useDashboardSections'

const props = defineProps<{
  sections: DashboardSection[]
  bounds: Record<string, SectionBounds>
}>()

function bandStyle(section: DashboardSection) {
  const b = props.bounds[section.id]
  if (!b) return {}
  return {
    top: `${b.top}px`,
    height: `${b.height}px`,
    background: `var(--section-${section.color})`,
    borderColor: `var(--section-${section.color}-line)`,
  }
}
</script>

<style scoped>
.section-bands {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.section-band {
  position: absolute;
  /* Cards sit 4px inside their grid item, so bleed 4px outward into the
     page padding for an 8px band-to-card gap matching the top/bottom. */
  left: -4px;
  right: -4px;
  border: 1px solid;
  border-radius: 14px;
  transition: top 0.2s ease, height 0.2s ease;
}
</style>
