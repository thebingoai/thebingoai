<template>
  <UiDialog :open="open" @update:open="$emit('update:open', $event)" title="Upload Documents" size="lg">
    <div class="space-y-4">
      <!-- Namespace Selection -->
      <UiSelect
        v-model="selectedNamespace"
        :options="namespaceOptions"
        label="Namespace"
        placeholder="Select namespace"
      />

      <!-- Tags Input -->
      <UiInput
        v-model="tags"
        label="Tags (optional)"
        placeholder="tag1, tag2, tag3"
        hint="Comma-separated tags for organization"
      />

      <!-- File Upload Zone -->
      <div>
        <label class="mb-1.5 block text-sm font-medium text-neutral-700 dark:text-neutral-300">
          Files
        </label>
        <UiFileUpload
          accept=".md,.markdown"
          multiple
          hint="Markdown files only (.md, .markdown)"
          @files-selected="handleFilesSelected"
        />
      </div>

      <!-- Upload Progress -->
      <div v-if="uploadQueue.length > 0" class="space-y-2">
        <h3 class="text-sm font-medium text-neutral-700 dark:text-neutral-300">
          Upload Progress
        </h3>
        <div
          v-for="upload in uploadQueue"
          :key="upload.id"
          class="rounded-lg border border-neutral-200 p-3 dark:border-neutral-800"
        >
          <div class="mb-2 flex items-center justify-between text-sm">
            <span class="truncate font-medium text-neutral-900 dark:text-neutral-100">
              {{ upload.file.name }}
            </span>
            <UiBadge
              :variant="getStatusVariant(upload.status)"
              size="sm"
            >
              {{ upload.status }}
            </UiBadge>
          </div>
          <UiProgressBar
            v-if="upload.status === 'uploading' || upload.status === 'processing'"
            :value="upload.progress"
            :animated="upload.status === 'processing'"
            size="sm"
          />
          <p v-if="upload.error" class="mt-2 text-sm text-error-600 dark:text-error-400">
            {{ upload.error }}
          </p>
        </div>
      </div>
    </div>

    <template #footer>
      <UiButton variant="outline" @click="$emit('update:open', false)">
        Close
      </UiButton>
    </template>
  </UiDialog>
</template>

<script setup lang="ts">
import type { UploadProgress } from '~/types'

interface Props {
  open: boolean
  namespaces: string[]
  defaultNamespace?: string
}

const props = withDefaults(defineProps<Props>(), {
  defaultNamespace: 'default'
})

const emit = defineEmits<{
  'update:open': [value: boolean]
  'upload-complete': []
}>()

const { uploadFile } = useUpload()
const uploads = useUpload().uploads

const selectedNamespace = ref(props.defaultNamespace)
const tags = ref('')
const uploadQueue = ref<UploadProgress[]>([])

const namespaceOptions = computed(() =>
  props.namespaces.map(ns => ({ label: ns, value: ns }))
)

const handleFilesSelected = async (files: File[]) => {
  for (const file of files) {
    try {
      await uploadFile(file, selectedNamespace.value, tags.value)
    } catch (error) {
      console.error('Upload error:', error)
    }
  }

  // Update upload queue from uploads map
  uploadQueue.value = Array.from(uploads.value.values())

  // Emit complete event when all uploads are done
  const allDone = uploadQueue.value.every(
    u => u.status === 'completed' || u.status === 'failed'
  )
  if (allDone) {
    emit('upload-complete')
  }
}

const getStatusVariant = (status: UploadProgress['status']) => {
  const variants = {
    pending: 'default' as const,
    uploading: 'primary' as const,
    processing: 'warning' as const,
    completed: 'success' as const,
    failed: 'error' as const
  }
  return variants[status]
}

// Reset on close
watch(() => props.open, (isOpen) => {
  if (!isOpen) {
    uploadQueue.value = []
    tags.value = ''
  }
})
</script>
