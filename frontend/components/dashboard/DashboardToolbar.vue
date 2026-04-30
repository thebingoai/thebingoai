<template>
  <div class="flex flex-shrink-0 items-center justify-between border-b border-[var(--line)] bg-[var(--paper-1)] px-6 py-2 gap-4 dark:border-neutral-700 dark:bg-neutral-900">
    <!-- Type pills -->
    <div class="flex items-center gap-1.5 flex-wrap">
      <!-- ADD -->
      <button
        class="add-pill"
        @click="emit('add-widget', 'kpi')"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        Add
      </button>

      <!-- KPI -->
      <button class="type-pill" @click="emit('add-widget', 'kpi')">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <rect x="3" y="13" width="4" height="8" rx="1"/>
          <rect x="10" y="9" width="4" height="12" rx="1"/>
          <rect x="17" y="5" width="4" height="16" rx="1"/>
        </svg>
        KPI
      </button>

      <!-- Chart -->
      <button class="type-pill" @click="emit('add-widget', 'chart')">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <polyline points="3 17 8 12 13 14 20 7"/>
          <circle cx="20" cy="7" r="1.5" fill="currentColor" stroke="none"/>
          <circle cx="13" cy="14" r="1.5" fill="currentColor" stroke="none"/>
          <circle cx="8" cy="12" r="1.5" fill="currentColor" stroke="none"/>
          <circle cx="3" cy="17" r="1.5" fill="currentColor" stroke="none"/>
        </svg>
        Chart
      </button>

      <!-- Table -->
      <button class="type-pill" @click="emit('add-widget', 'table')">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
          <line x1="3" y1="9" x2="21" y2="9"/>
          <line x1="3" y1="15" x2="21" y2="15"/>
          <line x1="9" y1="9" x2="9" y2="21"/>
        </svg>
        Table
      </button>

      <!-- Text -->
      <button class="type-pill" @click="emit('add-widget', 'text')">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <polyline points="4 7 4 4 20 4 20 7"/>
          <line x1="9" y1="20" x2="15" y2="20"/>
          <line x1="12" y1="4" x2="12" y2="20"/>
        </svg>
        Text
      </button>

      <!-- Filter -->
      <button class="type-pill" @click="emit('add-widget', 'filter')">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
        </svg>
        Filter
      </button>
    </div>

    <!-- Widget count -->
    <span v-if="widgetCount > 0" class="widget-count flex-shrink-0">
      {{ widgetCount }} widget{{ widgetCount !== 1 ? 's' : '' }}
    </span>
  </div>
</template>

<script setup lang="ts">
import type { WidgetType } from '~/types/dashboard'

defineProps<{
  widgetCount: number
}>()

const emit = defineEmits<{ 'add-widget': [type: WidgetType] }>()
</script>

<style scoped>
.add-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 11px;
  border-radius: 20px;
  font-family: var(--font-sans);
  font-size: 11.5px;
  font-weight: 600;
  border: 1px solid var(--ember);
  background: var(--ember);
  color: #fff;
  cursor: pointer;
  transition: opacity 0.1s;
  white-space: nowrap;
}
.add-pill:hover { opacity: 0.88; }

.type-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 20px;
  font-family: var(--font-sans);
  font-size: 11.5px;
  font-weight: 500;
  border: 1px solid var(--line);
  background: var(--paper-0);
  color: var(--ink-1);
  cursor: pointer;
  transition: border-color 0.1s, background 0.1s, color 0.1s;
  white-space: nowrap;
}
.type-pill:hover {
  border-color: var(--ember-soft);
  background: var(--ember-wash);
  color: var(--ember);
}

.widget-count {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--ink-3);
}
</style>
