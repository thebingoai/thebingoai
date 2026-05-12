<template>
  <div class="dash-table">
    <!-- Header row -->
    <div class="dash-table-head">
      <div class="dash-col dash-col-title">DASHBOARD</div>
      <div class="dash-col dash-col-thread">FROM THREAD</div>
      <div class="dash-col dash-col-schedule">SCHEDULE</div>
      <div class="dash-col dash-col-refreshed">REFRESHED</div>
      <div class="dash-col dash-col-owner">OWNER</div>
      <div class="dash-col dash-col-widgets">WIDGETS</div>
    </div>

    <!-- Data rows -->
    <button
      v-for="item in items"
      :key="item.id"
      class="dash-row"
      @click="$emit('open', item.id)"
    >
      <!-- Dashboard title -->
      <div class="dash-col dash-col-title">
        <span class="dash-title">{{ item.title }}</span>
      </div>

      <!-- From thread -->
      <div class="dash-col dash-col-thread">
        <button
          v-if="item.sourceTitle && item.sourceThreadId"
          class="dash-thread dash-thread--link"
          @click.stop="$emit('open-thread', item.sourceThreadId!)"
        >
          <Link2 class="h-3 w-3 flex-shrink-0" />
          <em class="dash-thread-label">"{{ item.sourceTitle }}"</em>
        </button>
        <span v-else-if="item.sourceTitle" class="dash-thread">
          <Link2 class="h-3 w-3 flex-shrink-0" />
          <em class="dash-thread-label">"{{ item.sourceTitle }}"</em>
        </span>
        <span v-else class="dash-muted">—</span>
      </div>

      <!-- Schedule -->
      <div class="dash-col dash-col-schedule">
        <template v-if="scheduleLabel(item)">
          <span class="dash-dot" :class="{ 'dash-dot--on': item.scheduleActive }" />
          <span class="dash-schedule-label">{{ scheduleLabel(item) }}</span>
        </template>
        <span v-else class="dash-muted">—</span>
      </div>

      <!-- Refreshed -->
      <div class="dash-col dash-col-refreshed dash-muted">
        {{ item.updatedAt ? timeAgo(item.updatedAt) : '—' }}
      </div>

      <!-- Owner -->
      <div class="dash-col dash-col-owner">
        <span class="dash-avatar">{{ ownerInitial }}</span>
        <span class="dash-owner-handle">@{{ ownerHandle }}</span>
      </div>

      <!-- Widget count -->
      <div class="dash-col dash-col-widgets dash-widgets-num">
        {{ item.widgetCount }}
      </div>
    </button>

    <!-- Empty filtered state -->
    <div v-if="items.length === 0" class="dash-empty">
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

const ownerHandle = computed(() => {
  const local = props.currentUserEmail.split('@')[0] ?? ''
  return local
})

const ownerInitial = computed(() => {
  return ownerHandle.value.charAt(0).toUpperCase()
})

function scheduleLabel(item: DashboardListItem): string | null {
  if (item.cronExpression) return item.cronExpression
  if (item.scheduleValue) return item.scheduleValue
  return null
}
</script>

<style scoped>
/* ── Table layout (CSS grid so all rows share column widths) ── */
.dash-table {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
  background: var(--paper-0);
}

/* Shared column grid — 6 columns */
.dash-table-head,
.dash-row {
  display: grid;
  grid-template-columns:
    minmax(160px, 2.2fr)   /* DASHBOARD */
    minmax(140px, 2.4fr)   /* FROM THREAD */
    minmax(120px, 1.4fr)   /* SCHEDULE */
    minmax(80px,  1fr)     /* REFRESHED */
    minmax(100px, 1.2fr)   /* OWNER */
    56px;                  /* WIDGETS */
  align-items: center;
  gap: 0;
}

/* ── Header ── */
.dash-table-head {
  padding: 10px 20px;
  border-bottom: 1px solid var(--line);
  background: var(--paper-1);
}

.dash-table-head .dash-col {
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 500;
  letter-spacing: 0.08em;
  color: var(--ink-3);
  text-transform: uppercase;
}

/* ── Rows ── */
.dash-row {
  padding: 12px 20px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  width: 100%;
  background: transparent;
  cursor: pointer;
  font-family: var(--font-sans);
  transition: background 0.1s;
}
.dash-row:last-child {
  border-bottom: none;
}
.dash-row:hover {
  background: var(--paper-1);
}

/* ── Column cells ── */
.dash-col {
  font-size: 13px;
  color: var(--ink-0);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.dash-col-widgets {
  justify-content: flex-end;
  padding-right: 0;
  font-family: var(--font-mono);
  font-size: 12.5px;
  color: var(--ink-1);
}

/* ── Dashboard title ── */
.dash-title {
  font-weight: 500;
  color: var(--ink-0);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dash-row:hover .dash-title {
  color: var(--ember);
}

/* ── FROM THREAD ── */
.dash-thread {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--ink-2);
  overflow: hidden;
}

.dash-thread--link {
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  max-width: 100%;
  overflow: hidden;
}
.dash-thread--link:hover .dash-thread-label {
  color: var(--ember);
  text-decoration: underline;
  text-decoration-color: var(--ember);
}
.dash-thread-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-style: italic;
  font-size: 12.5px;
}

/* ── Schedule ── */
.dash-dot {
  flex-shrink: 0;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ink-3);
}
.dash-dot--on {
  background: var(--ember);
}

.dash-schedule-label {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-1);
  white-space: nowrap;
}

/* ── Owner ── */
.dash-avatar {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--ember-wash, color-mix(in srgb, var(--ember) 15%, transparent));
  color: var(--ember);
  font-size: 10px;
  font-weight: 600;
  font-family: var(--font-sans);
}

.dash-owner-handle {
  font-size: 12.5px;
  color: var(--ink-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Muted text ── */
.dash-muted {
  color: var(--ink-3);
  font-size: 12.5px;
}

.dash-widgets-num {
  font-weight: 500;
}

/* ── Empty filtered state ── */
.dash-empty {
  padding: 32px 20px;
  text-align: center;
  font-size: 13px;
  color: var(--ink-3);
}
</style>
