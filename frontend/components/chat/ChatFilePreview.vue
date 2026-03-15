<template>
  <div
    class="relative flex items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-800"
    :class="isImage ? 'h-16 w-16 p-0 overflow-hidden' : 'h-12 px-3 py-2 max-w-48'"
  >
    <!-- Image thumbnail -->
    <template v-if="isImage">
      <img
        v-if="file.preview_url"
        :src="file.preview_url"
        :alt="file.file.name"
        class="h-full w-full object-cover"
      />
      <div
        v-else
        class="flex h-full w-full items-center justify-center bg-neutral-100 dark:bg-neutral-700"
      >
        <component :is="ImageIcon" class="h-6 w-6 text-neutral-400 dark:text-neutral-500" />
      </div>
    </template>

    <!-- Document icon + metadata -->
    <template v-else>
      <component
        :is="fileIcon"
        class="h-5 w-5 flex-shrink-0 text-neutral-500 dark:text-neutral-400"
      />
      <div class="min-w-0 flex-1">
        <p class="truncate text-xs font-medium text-neutral-800 dark:text-neutral-200">
          {{ file.file.name }}
        </p>
        <p class="text-xs text-neutral-500 dark:text-neutral-400">
          {{ formattedSize }}
        </p>
      </div>
    </template>

    <!-- Status overlays -->

    <!-- Uploading spinner -->
    <div
      v-if="file.status === 'uploading'"
      class="absolute inset-0 flex items-center justify-center rounded-lg bg-white/70 dark:bg-neutral-900/70"
    >
      <svg
        class="h-4 w-4 animate-spin text-neutral-600 dark:text-neutral-300"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          class="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          stroke-width="4"
        />
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
    </div>

    <!-- Error indicator -->
    <div
      v-else-if="file.status === 'error'"
      class="absolute inset-0 flex items-center justify-center rounded-lg bg-red-50/80 dark:bg-red-950/60"
      :title="file.error ?? 'Upload failed'"
    >
      <component
        :is="AlertCircle"
        class="h-4 w-4 text-red-500 dark:text-red-400"
      />
    </div>

    <!-- Remove button — shown on hover, always visible when error/uploading is not active -->
    <button
      v-if="file.status !== 'uploading'"
      type="button"
      class="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-neutral-600 text-white opacity-0 transition-opacity group-hover:opacity-100 hover:bg-neutral-800 dark:bg-neutral-500 dark:hover:bg-neutral-300 dark:hover:text-neutral-900"
      :title="`Remove ${file.file.name}`"
      @click.stop="emit('remove', index)"
    >
      <component :is="X" class="h-2.5 w-2.5" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { Image as ImageIcon, FileText, FileSpreadsheet, File, AlertCircle, X } from 'lucide-vue-next'
import type { FileAttachment } from '~/composables/useChatFileUpload'

interface Props {
  file: FileAttachment
  index: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  remove: [index: number]
}>()

const IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/gif', 'image/webp'])

const isImage = computed(() => IMAGE_TYPES.has(props.file.file.type))

const fileIcon = computed(() => {
  const type = props.file.file.type
  if (type === 'text/csv') return FileSpreadsheet
  if (type === 'application/pdf') return FileText
  if (type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') return FileText
  return File
})

const formattedSize = computed(() => {
  const bytes = props.file.file.size
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
})
</script>
