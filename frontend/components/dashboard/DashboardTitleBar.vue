<template>
  <div class="flex flex-shrink-0 flex-col border-b border-[var(--line)] bg-[var(--paper-0)] px-6 pt-5 pb-0 dark:bg-neutral-900 dark:border-neutral-700">

    <!-- Back nav -->
    <button
      class="back-link mb-2"
      @click="emit('back')"
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="15 18 9 12 15 6"/>
      </svg>
      Dashboards
    </button>

    <!-- Title row -->
    <div class="flex items-start justify-between gap-4">
      <!-- Title -->
      <div class="flex items-center gap-2 min-w-0">
        <input
          v-if="editMode && isEditingTitle"
          ref="titleInput"
          v-model="editTitle"
          class="dash-title-input"
          @blur="saveTitle"
          @keydown.enter="saveTitle"
          @keydown.escape="cancelEdit"
        />
        <h1
          v-else
          class="dash-title"
          :class="editMode ? 'cursor-pointer hover:opacity-70 transition-opacity' : ''"
          @click="editMode && startEditTitle()"
        >{{ title }}</h1>
        <!-- Dirty dot -->
        <span
          v-if="dirty"
          class="h-1.5 w-1.5 rounded-full bg-amber-400 flex-shrink-0 mt-2"
          title="Unsaved changes"
        />
      </div>

      <!-- Action buttons -->
      <div class="flex items-center gap-1.5 flex-shrink-0 pt-1">
        <!-- View mode -->
        <template v-if="!editMode">
          <DashboardSchedulePopover v-if="dashboardId" :dashboard-id="dashboardId" />
          <BriefMeButton v-if="dashboardId" :dashboard-id="dashboardId" />
          <button
            class="hdr-btn"
            :disabled="refreshing"
            @click="emit('refresh-all')"
          >
            <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': refreshing }" />
            <span class="hidden sm:inline">{{ refreshing ? 'Refreshing…' : 'Refresh all' }}</span>
          </button>
          <button class="hdr-btn" @click="emit('share')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>
              <polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/>
            </svg>
            <span class="hidden sm:inline">Share</span>
          </button>
          <button class="hdr-btn hdr-btn--filled" @click="emit('toggle-edit')">
            <Pencil class="h-3.5 w-3.5" />
            <span class="hidden sm:inline">Edit</span>
          </button>
        </template>

        <!-- Edit mode -->
        <template v-else>
          <button
            class="hdr-btn hdr-btn--danger"
            @click="emit('delete')"
          >
            <Trash2 class="h-3.5 w-3.5" />
            <span class="hidden sm:inline">Delete</span>
          </button>
          <button
            class="hdr-btn"
            :class="dirty && !saving ? 'hdr-btn--save' : 'hdr-btn--disabled'"
            :disabled="!dirty || saving"
            @click="emit('save')"
          >
            <Save class="h-3.5 w-3.5" />
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
          <button class="hdr-btn hdr-btn--filled" @click="emit('toggle-edit')">
            <Eye class="h-3.5 w-3.5" />
            <span class="hidden sm:inline">Done</span>
          </button>
        </template>
      </div>
    </div>

    <!-- Meta subtitle -->
    <div v-if="sourceTitle || lastRefreshedAt" class="dash-meta">
      <template v-if="sourceTitle">
        Built from
        <a
          v-if="sourceHref"
          :href="sourceHref"
          class="dash-meta-link"
        >{{ sourceTitle }}</a>
        <span v-else class="dash-meta-link cursor-default">{{ sourceTitle }}</span>
        <template v-if="lastRefreshedAt"> · last refreshed {{ formatRelativeTime(lastRefreshedAt) }}</template>
      </template>
      <template v-else-if="lastRefreshedAt">
        Last refreshed {{ formatRelativeTime(lastRefreshedAt) }}
      </template>
    </div>

    <div class="pb-3" />
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { Pencil, Eye, Save, RefreshCw, Trash2 } from 'lucide-vue-next'

const props = defineProps<{
  title: string
  editMode: boolean
  dirty: boolean
  saving: boolean
  refreshing: boolean
  dashboardId?: number
  sourceTitle?: string
  sourceHref?: string
  lastRefreshedAt?: string
}>()

const emit = defineEmits<{
  back: []
  'toggle-edit': []
  save: []
  'refresh-all': []
  delete: []
  share: []
  analyze: []
  'update:title': [value: string]
}>()

const titleInput = ref<HTMLInputElement>()
const isEditingTitle = ref(false)
const editTitle = ref('')

const startEditTitle = () => {
  editTitle.value = props.title
  isEditingTitle.value = true
  nextTick(() => {
    const el = titleInput.value
    if (!el) return
    el.focus()
    el.select()
    el.scrollLeft = 0
  })
}

const saveTitle = () => {
  if (!isEditingTitle.value) return
  isEditingTitle.value = false
  const newTitle = editTitle.value.trim()
  if (newTitle && newTitle !== props.title) {
    emit('update:title', newTitle)
  }
}

const cancelEdit = () => {
  isEditingTitle.value = false
}

function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}
</script>

<style scoped>
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  color: var(--ink-3);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  transition: color 0.1s;
}
.back-link:hover { color: var(--ink-1); }

.dash-title {
  font-family: var(--font-display);
  font-style: normal;
  font-weight: 400;
  font-size: 30px;
  line-height: 1.05;
  letter-spacing: -0.2px;
  color: var(--ink-0);
  font-optical-sizing: auto;
  font-variation-settings: 'opsz' 72;
  margin: 0;
}

.dash-title-input {
  font-family: var(--font-display);
  font-style: normal;
  font-weight: 400;
  font-size: 30px;
  line-height: 1.05;
  color: var(--ink-0);
  font-optical-sizing: auto;
  font-variation-settings: 'opsz' 72;
  background: transparent;
  border: none;
  border-bottom: 2px solid var(--ember);
  outline: none;
  width: 100%;
  max-width: 500px;
}

.dash-meta {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--ink-3);
  margin-top: 4px;
}
.dash-meta-link {
  color: var(--ember);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.dash-meta-link:hover { opacity: 0.8; }

/* Header action buttons */
.hdr-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 8px;
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--line);
  background: var(--paper-0);
  color: var(--ink-1);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.1s, border-color 0.1s;
}
.hdr-btn:hover { background: var(--paper-2); }
.hdr-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.hdr-btn--filled {
  background: var(--paper-2);
  border-color: var(--line);
}

.hdr-btn--save {
  background: var(--ember);
  border-color: var(--ember);
  color: #fff;
}
.hdr-btn--save:hover { opacity: 0.88; background: var(--ember); }

.hdr-btn--danger {
  color: var(--ink-2);
}
.hdr-btn--danger:hover {
  background: #fff1f2;
  border-color: #fecdd3;
  color: #e11d48;
}

.hdr-btn--disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
