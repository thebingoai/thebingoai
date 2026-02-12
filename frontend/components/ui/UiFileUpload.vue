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
      <div class="rounded-full bg-neutral-100 p-3 dark:bg-neutral-800">
        <component :is="Upload" class="h-6 w-6 text-neutral-600 dark:text-neutral-400" />
      </div>

      <div class="text-center">
        <p class="text-sm font-medium text-neutral-900 dark:text-neutral-100">
          <span class="text-brand-600 dark:text-brand-400">Click to upload</span>
          or drag and drop
        </p>
        <p v-if="hint" class="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
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
      ? 'border-brand-500 bg-brand-50 dark:border-brand-400 dark:bg-brand-900/10'
      : 'border-neutral-300 hover:border-neutral-400 dark:border-neutral-700 dark:hover:border-neutral-600'
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
