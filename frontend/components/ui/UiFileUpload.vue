<template>
  <div
    ref="dropzoneRef"
    :class="dropzoneClasses"
    @click="openFileDialog"
    @dragenter.prevent="isDragging = true"
    @dragover.prevent
    @dragleave.prevent="isDragging = false"
    @drop.prevent="handleDrop"
  >
    <input
      ref="fileInputRef"
      type="file"
      :accept="accept"
      :multiple="multiple"
      class="hidden"
      @change="handleFileSelect"
    />

    <div class="flex flex-col items-center justify-center gap-3">
      <div class="rounded-full bg-gray-100 dark:bg-neutral-700 p-3">
        <component :is="Upload" class="h-6 w-6 text-gray-600 dark:text-neutral-400" />
      </div>

      <div class="text-center">
        <p class="text-sm font-light text-gray-900 dark:text-neutral-200">
          <span class="text-gray-600 dark:text-neutral-400">Click to upload</span>
          or drag and drop
        </p>
        <p v-if="hint" class="mt-1 text-xs text-gray-500 dark:text-neutral-500">
          {{ hint }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Upload } from 'lucide-vue-next'
import { cn } from '~/utils/cn'

interface Props {
  accept?: string
  multiple?: boolean
  hint?: string
}

const props = withDefaults(defineProps<Props>(), {
  multiple: false
})

const emit = defineEmits<{
  'files-selected': [files: File[]]
}>()

const dropzoneRef = ref<HTMLElement>()
const fileInputRef = ref<HTMLInputElement>()
const isDragging = ref(false)

const dropzoneClasses = computed(() =>
  cn(
    'relative flex min-h-[200px] cursor-pointer items-center justify-center rounded-lg border-2 border-dashed transition-colors',
    isDragging.value
      ? 'border-gray-500 bg-gray-50 dark:border-neutral-500 dark:bg-neutral-800'
      : 'border-gray-300 hover:border-gray-400 dark:border-neutral-600 dark:hover:border-neutral-500'
  )
)

const openFileDialog = () => {
  fileInputRef.value?.click()
}

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  const files = Array.from(target.files || [])
  if (files.length > 0) {
    emit('files-selected', files)
  }
  // Reset input
  target.value = ''
}

const handleDrop = (event: DragEvent) => {
  isDragging.value = false
  const files = Array.from(event.dataTransfer?.files || [])
  if (files.length > 0) {
    emit('files-selected', files)
  }
}
</script>
