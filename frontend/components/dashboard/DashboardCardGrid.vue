<template>
  <div class="dashboard-card-grid">
    <button
      v-for="item in items"
      :key="item.id"
      class="dash-card"
      @click="$emit('open', item.id)"
    >
      <!-- Head: title + widget count -->
      <div class="dash-card-head">
        <span class="dash-card-title">{{ item.title }}</span>
        <span class="dash-card-widgets">{{ item.widgetCount }}</span>
      </div>

      <!-- From thread -->
      <button
        v-if="item.sourceTitle && item.sourceThreadId"
        class="dash-card-thread dash-card-thread--link"
        @click.stop="$emit('open-thread', item.sourceThreadId!)"
      >
        <Link2 class="h-3 w-3 flex-shrink-0" />
        <em class="dash-card-thread-label">"{{ item.sourceTitle }}"</em>
      </button>
      <span v-else-if="item.sourceTitle" class="dash-card-thread">
        <Link2 class="h-3 w-3 flex-shrink-0" />
        <em class="dash-card-thread-label">"{{ item.sourceTitle }}"</em>
      </span>
      <span v-else class="dash-card-muted">—</span>

      <!-- Meta row: schedule + refreshed -->
      <div class="dash-card-meta">
        <template v-if="scheduleLabel(item)">
          <span class="dash-dot" :class="{ 'dash-dot--on': item.scheduleActive }" />
          <span class="dash-card-schedule">{{ scheduleLabel(item) }}</span>
        </template>
        <span v-else class="dash-card-muted">No schedule</span>
        <span class="dash-card-spacer" />
        <span class="dash-card-refreshed">{{ item.updatedAt ? timeAgo(item.updatedAt) : '—' }}</span>
      </div>

      <!-- Owner -->
      <div class="dash-card-owner">
        <span class="dash-avatar">{{ ownerInitial }}</span>
        <span class="dash-card-owner-handle">@{{ ownerHandle }}</span>
      </div>
    </button>

    <div v-if="items.length === 0" class="dash-grid-empty">
      No dashboards match your search.
    </div>
  </div>
</template>

<script setup lang="ts">
import { Link2 } from 'lucide-vue-next'
import { timeAgo } from '~/utils/format'
import type { DashboardListItem } from '~/types/dashboard'

const props = defineProps<{
  items: DashboardListItem[]
  currentUserEmail: string
}>()

defineEmits<{ open: [id: number]; 'open-thread': [threadId: string] }>()

const ownerHandle = computed(() => props.currentUserEmail.split('@')[0] ?? '')
const ownerInitial = computed(() => ownerHandle.value.charAt(0).toUpperCase())

function scheduleLabel(item: DashboardListItem): string | null {
  if (item.cronExpression) return item.cronExpression
  if (item.scheduleValue) return item.scheduleValue
  return null
}
</script>

<style scoped>
.dashboard-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

/* ── Card ── */
.dash-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  background: var(--paper-0);
  border: 1px solid var(--line);
  border-radius: 12px;
  text-align: left;
  cursor: pointer;
  transition: background 0.1s, border-color 0.1s, box-shadow 0.1s;
  font-family: var(--font-sans);
  width: 100%;
  min-height: 0;
}
.dash-card:hover {
  background: var(--paper-1);
  border-color: var(--line-2);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

/* ── Head ── */
.dash-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.dash-card-title {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--ink-0);
  line-height: 1.35;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.dash-card:hover .dash-card-title {
  color: var(--ember);
}

.dash-card-widgets {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  color: var(--ink-2);
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 1px 6px;
  margin-top: 1px;
}

/* ── FROM THREAD ── */
.dash-card-thread {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--ink-2);
  overflow: hidden;
  font-size: 12px;
  font-family: var(--font-sans);
}

.dash-card-thread--link {
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  text-align: left;
  max-width: 100%;
}
.dash-card-thread--link:hover .dash-card-thread-label {
  color: var(--ember);
  text-decoration: underline;
  text-decoration-color: var(--ember);
}

.dash-card-thread-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-style: italic;
  font-size: 12px;
}

/* ── Meta row ── */
.dash-card-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 2px;
}

.dash-card-spacer { flex: 1; }

.dash-dot {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ink-3);
}
.dash-dot--on { background: var(--ember); }

.dash-card-schedule {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dash-card-refreshed {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-3);
  white-space: nowrap;
}

.dash-card-muted {
  font-size: 12px;
  color: var(--ink-3);
}

/* ── Owner ── */
.dash-card-owner {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 2px;
}

.dash-avatar {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--ember-wash, color-mix(in srgb, var(--ember) 15%, transparent));
  color: var(--ember);
  font-size: 9px;
  font-weight: 600;
  font-family: var(--font-sans);
}

.dash-card-owner-handle {
  font-size: 11.5px;
  color: var(--ink-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Empty ── */
.dash-grid-empty {
  grid-column: 1 / -1;
  padding: 32px 20px;
  text-align: center;
  font-size: 13px;
  color: var(--ink-3);
}
</style>
