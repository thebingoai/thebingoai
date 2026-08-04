<template>
  <nav v-if="sections.length >= 2" class="section-nav">
    <button
      v-for="section in sections"
      :key="section.id"
      class="section-nav-pill"
      :title="section.title"
      @click="jump(section.id)"
    >
      <span class="section-nav-dot" :style="{ background: `var(--section-${section.color}-line)` }" />
      {{ section.title || 'Untitled section' }}
    </button>
  </nav>
</template>

<script setup lang="ts">
import type { DashboardSection, SectionBounds } from '~/composables/useDashboardSections'

const props = defineProps<{
  sections: DashboardSection[]
  bounds: Record<string, SectionBounds>
  /** The grid wrapper element the bounds are relative to. */
  gridWrapper: HTMLElement | null
}>()

function scrollContainer(): HTMLElement | null {
  const wrapper = props.gridWrapper
  return wrapper?.closest<HTMLElement>('[data-dashboard-scroll]')
    ?? wrapper?.closest<HTMLElement>('.overflow-y-auto')
    ?? null
}

/** Section top in the scroll container's scroll coordinates. */
function sectionScrollTop(id: string): number | null {
  const wrapper = props.gridWrapper
  const container = scrollContainer()
  const b = props.bounds[id]
  if (!wrapper || !container || !b) return null
  const wrapperTop = wrapper.getBoundingClientRect().top
    - container.getBoundingClientRect().top
    + container.scrollTop
  return wrapperTop + b.top
}

// The bar sits outside the scroll viewport — only a small breathing offset.
const JUMP_OFFSET = 10

function jump(id: string) {
  const container = scrollContainer()
  const top = sectionScrollTop(id)
  if (!container || top === null) return
  container.scrollTo({ top: Math.max(0, top - JUMP_OFFSET), behavior: 'smooth' })
}
</script>

<style scoped>
.section-nav {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding: 8px 24px;
  background: var(--paper-0);
  border-bottom: 1px solid var(--line);
}
.section-nav-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 11px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--paper-0);
  color: var(--ink-1);
  font-family: var(--font-sans);
  font-size: 12.5px;
  font-weight: 500;
  white-space: nowrap;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  transition: background 0.1s, color 0.1s, border-color 0.1s;
}
.section-nav-pill:hover {
  background: var(--paper-1);
  border-color: var(--line-2);
}
.section-nav-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>
