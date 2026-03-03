<template>
  <div class="flex flex-shrink-0 items-center justify-between px-6 py-3 border-b border-gray-100 bg-white">
    <!-- Left: back + breadcrumb -->
    <div class="flex items-center gap-2 min-w-0">
      <button
        class="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-700 transition-colors flex-shrink-0"
        @click="emit('back')"
      >
        <ChevronLeft class="h-4 w-4" />
        <span>Dashboards</span>
      </button>
      <span class="text-gray-300">/</span>
      <span class="text-sm font-medium text-gray-800 truncate">{{ title }}</span>
      <!-- Dirty indicator dot -->
      <span
        v-if="dirty"
        class="h-1.5 w-1.5 rounded-full bg-amber-400 flex-shrink-0"
        title="Unsaved changes"
      />
    </div>

    <!-- Right: save + edit toggle -->
    <div class="flex items-center gap-2 flex-shrink-0">
      <!-- Save button — only visible in edit mode -->
      <button
        v-if="editMode"
        class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
        :class="dirty && !saving
          ? 'bg-indigo-600 text-white hover:bg-indigo-700'
          : 'bg-gray-100 text-gray-400 cursor-not-allowed'"
        :disabled="!dirty || saving"
        @click="emit('save')"
      >
        <Save class="h-3.5 w-3.5" />
        {{ saving ? 'Saving...' : 'Save' }}
      </button>

      <button
        class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
        :class="editMode
          ? 'bg-gray-900 text-white hover:bg-gray-700'
          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
        @click="emit('toggle-edit')"
      >
        <component :is="editMode ? Eye : Pencil" class="h-3.5 w-3.5" />
        {{ editMode ? 'View' : 'Edit' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ChevronLeft, Pencil, Eye, Save } from 'lucide-vue-next'

defineProps<{
  title: string
  editMode: boolean
  dirty: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  back: []
  'toggle-edit': []
  save: []
}>()
</script>
