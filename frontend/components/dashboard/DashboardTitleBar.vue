<template>
  <div class="flex flex-shrink-0 flex-col md:flex-row md:items-center md:justify-between px-3 md:px-6 py-3 gap-2 border-b border-gray-100 bg-white dark:bg-neutral-900 dark:border-neutral-700">
    <!-- Left: back + breadcrumb -->
    <div class="flex items-center gap-2 min-w-0">
      <button
        class="flex items-center gap-1.5 text-sm font-semibold text-orange-500 hover:text-orange-600 transition-colors flex-shrink-0"
        @click="emit('back')"
      >
        <ChevronLeft class="h-4 w-4" />
        <span>Dashboards</span>
      </button>
      <span class="text-gray-300 dark:text-neutral-600">/</span>
      <input
        v-if="editMode && isEditingTitle"
        ref="titleInput"
        v-model="editTitle"
        @blur="saveTitle"
        @keydown.enter="saveTitle"
        @keydown.escape="cancelEdit"
        class="text-sm font-medium text-gray-800 bg-transparent border-b border-gray-300 outline-none w-full md:w-[400px] dark:text-neutral-100 dark:border-neutral-600"
      />
      <span
        v-else
        class="text-sm font-medium text-gray-800 truncate dark:text-neutral-100"
        :class="editMode ? 'cursor-pointer hover:text-gray-900 dark:hover:text-white' : ''"
        @click="editMode && startEditTitle()"
      >{{ title }}</span>
      <!-- Dirty indicator dot -->
      <span
        v-if="dirty"
        class="h-1.5 w-1.5 rounded-full bg-amber-400 flex-shrink-0"
        title="Unsaved changes"
      />
    </div>

    <!-- Right: refresh all + schedule + save + edit toggle -->
    <div class="flex items-center gap-2 flex-shrink-0">
      <!-- Refresh All button — visible in view mode -->
      <button
        v-if="!editMode"
        class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors bg-gray-100 text-gray-600 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed dark:bg-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-600"
        :disabled="refreshing"
        @click="emit('refresh-all')"
      >
        <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': refreshing }" />
        <span class="hidden sm:inline">{{ refreshing ? 'Refreshing...' : 'Refresh All' }}</span>
      </button>

      <!-- Analyze button — visible in view mode -->
      <button
        v-if="!editMode"
        class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors bg-indigo-50 text-indigo-600 hover:bg-indigo-100 dark:bg-indigo-900/30 dark:text-indigo-400 dark:hover:bg-indigo-900/50"
        @click="emit('analyze')"
      >
        <BarChart2 class="h-3.5 w-3.5" />
        <span class="hidden sm:inline">Analyze</span>
      </button>

      <!-- Schedule popover — visible in view mode -->
      <DashboardSchedulePopover v-if="!editMode && dashboardId" :dashboard-id="dashboardId" />

      <!-- Delete button — only visible in edit mode -->
      <button
        v-if="editMode"
        class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors bg-gray-100 text-gray-500 hover:bg-red-50 hover:text-red-600 dark:bg-neutral-700 dark:text-neutral-400 dark:hover:bg-red-900/40 dark:hover:text-red-400"
        @click="emit('delete')"
      >
        <Trash2 class="h-3.5 w-3.5" />
        Delete
      </button>

      <!-- Save button — only visible in edit mode -->
      <button
        v-if="editMode"
        class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
        :class="dirty && !saving
          ? 'bg-indigo-600 text-white hover:bg-indigo-700'
          : 'bg-gray-100 text-gray-400 cursor-not-allowed dark:bg-neutral-700 dark:text-neutral-500'"
        :disabled="!dirty || saving"
        @click="emit('save')"
      >
        <Save class="h-3.5 w-3.5" />
        {{ saving ? 'Saving...' : 'Save' }}
      </button>

      <button
        class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
        :class="editMode
          ? 'bg-gray-900 text-white hover:bg-gray-700 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-white'
          : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-600'"
        @click="emit('toggle-edit')"
      >
        <component :is="editMode ? Eye : Pencil" class="h-3.5 w-3.5" />
        {{ editMode ? 'View' : 'Edit' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { ChevronLeft, Pencil, Eye, Save, RefreshCw, Trash2, BarChart2 } from 'lucide-vue-next'

const props = defineProps<{
  title: string
  editMode: boolean
  dirty: boolean
  saving: boolean
  refreshing: boolean
  dashboardId?: number
}>()

const emit = defineEmits<{
  back: []
  'toggle-edit': []
  save: []
  'refresh-all': []
  delete: []
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
</script>
