export interface UploadingFile {
  file: File
  file_id: string | null
  connection_id?: number | null  // for dataset files uploaded via connections API
  preview_url: string | null  // object URL for images
  status: 'uploading' | 'ready' | 'error'
  error?: string
  progress?: number  // 0-100, only meaningful when status === 'uploading'
}

interface FileRejection {
  name: string
  error: string
}

const MAX_FILE_COUNT = 5

const ACCEPTED_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
  'text/csv',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
])

const IMAGE_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
])

const DATASET_TYPES = new Set([
  'text/csv',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
])

// Extension-to-MIME fallback for drag-and-drop where browsers may report
// incorrect or empty MIME types (e.g. CSV as 'text/plain' or '').
const EXTENSION_TO_MIME: Record<string, string> = {
  csv: 'text/csv',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  webp: 'image/webp',
}

function resolveFileType(file: File): string | null {
  if (ACCEPTED_TYPES.has(file.type)) return file.type
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (ext && ext in EXTENSION_TO_MIME) return EXTENSION_TO_MIME[ext]
  return null
}

// Module-level singleton state (shared across all callers)
const attachedFiles = ref<UploadingFile[]>([])

const allFilesReady = computed<boolean>(() => {
  return attachedFiles.value.length > 0 && attachedFiles.value.every(f => f.status === 'ready')
})

export const useChatFileUpload = () => {
  const api = useApi()
  const chatStore = useChatStore()
  const config = useRuntimeConfig()
  const maxFileSizeBytes = config.public.chatFileMaxSizeMb * 1024 * 1024

  /** Ensure a conversation exists for file uploads, creating one if needed. */
  const ensureThread = async (): Promise<string> => {
    if (chatStore.currentThreadId) return chatStore.currentThreadId

    const chatApi = api.chat as any
    const { thread_id: tid } = await chatApi.createConversation() as { thread_id: string }
    chatStore.setCurrentThread(tid)
    chatStore.addConversation({
      id: tid,
      title: 'File Upload',
      type: 'task',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 0,
    })
    return tid
  }

  const addFiles = async (files: File[]): Promise<FileRejection[]> => {
    const rejections: FileRejection[] = []
    const validFiles: File[] = []
    const resolvedTypes = new Map<File, string>()

    // Check count limit first
    const currentCount = attachedFiles.value.length
    const slotsAvailable = MAX_FILE_COUNT - currentCount

    for (const file of files) {
      if (validFiles.length >= slotsAvailable) {
        rejections.push({
          name: file.name,
          error: `Cannot attach more than ${MAX_FILE_COUNT} files`,
        })
        continue
      }

      const resolvedType = resolveFileType(file)
      if (!resolvedType) {
        rejections.push({ name: file.name, error: 'Unsupported file type' })
        continue
      }

      if (file.size > maxFileSizeBytes) {
        rejections.push({ name: file.name, error: `File size exceeds ${config.public.chatFileMaxSizeMb}MB limit` })
        continue
      }

      resolvedTypes.set(file, resolvedType)
      validFiles.push(file)
    }

    if (validFiles.length === 0) {
      return rejections
    }

    // Split files: datasets (CSV/Excel) use connections API, others use chat files API
    const datasetFiles = validFiles.filter(f => DATASET_TYPES.has(resolvedTypes.get(f)!))
    const otherFiles = validFiles.filter(f => !DATASET_TYPES.has(resolvedTypes.get(f)!))

    // Build attachment objects with initial status and preview URLs
    const newAttachments: UploadingFile[] = validFiles.map(file => ({
      file,
      file_id: null,
      connection_id: null,
      preview_url: IMAGE_TYPES.has(resolvedTypes.get(file)!) ? URL.createObjectURL(file) : null,
      status: 'uploading' as const,
      progress: 0,
    }))

    const startIndex = attachedFiles.value.length
    attachedFiles.value = [...attachedFiles.value, ...newAttachments]

    // Helper to update progress for a specific file
    const updateProgress = (fileIndex: number, percent: number) => {
      const updated = [...attachedFiles.value]
      if (updated[fileIndex]?.status === 'uploading') {
        updated[fileIndex] = { ...updated[fileIndex], progress: percent }
        attachedFiles.value = updated
      }
    }

    const markReady = (fileIndex: number, extra: Partial<UploadingFile>) => {
      const updated = [...attachedFiles.value]
      if (updated[fileIndex]) {
        updated[fileIndex] = { ...updated[fileIndex], ...extra, status: 'ready' }
        attachedFiles.value = updated
      }
    }

    const markError = (fileIndex: number, error: string) => {
      const updated = [...attachedFiles.value]
      if (updated[fileIndex]) {
        updated[fileIndex] = { ...updated[fileIndex], status: 'error', error }
        attachedFiles.value = updated
      }
    }

    // Upload dataset files via connections API (reuses existing proven endpoint)
    for (const file of datasetFiles) {
      const idx = startIndex + validFiles.indexOf(file)
      try {
        const threadId = await ensureThread()
        const connectionsApi = api.connections as any
        const result = await connectionsApi.uploadDataset(
          file,
          undefined,
          (percent: number) => updateProgress(idx, percent),
          threadId,
        ) as { id: number; name: string; row_count: number }
        markReady(idx, { file_id: `connection:${result.id}`, connection_id: result.id })
      } catch (err: any) {
        markError(idx, err?.message || 'Dataset upload failed')
      }
    }

    // Upload non-dataset files via chat files API
    if (otherFiles.length > 0) {
      try {
        const chatApi = api.chat as any
        const response = await chatApi.uploadChatFiles(
          otherFiles,
          (percent: number) => {
            for (const file of otherFiles) {
              const idx = startIndex + validFiles.indexOf(file)
              updateProgress(idx, percent)
            }
          },
          chatStore.currentThreadId || null
        ) as { files: Array<{ file_id: string; thread_id: string }>; thread_id: string }

        // Handle auto-created conversation
        if (response.thread_id && !chatStore.currentThreadId) {
          chatStore.setCurrentThread(response.thread_id)
          chatStore.addConversation({
            id: response.thread_id,
            title: 'File Upload',
            type: 'task',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            message_count: 0,
          })
        }

        response.files.forEach((fileResult, i) => {
          const idx = startIndex + validFiles.indexOf(otherFiles[i])
          markReady(idx, { file_id: fileResult.file_id })
        })
      } catch (err: any) {
        for (const file of otherFiles) {
          const idx = startIndex + validFiles.indexOf(file)
          markError(idx, err?.message || 'Upload failed')
        }
      }
    }

    return rejections
  }

  const removeFile = (index: number) => {
    const file = attachedFiles.value[index]
    if (file?.preview_url) {
      URL.revokeObjectURL(file.preview_url)
    }
    attachedFiles.value = attachedFiles.value.filter((_, i) => i !== index)
  }

  const clearFiles = () => {
    for (const file of attachedFiles.value) {
      if (file.preview_url) {
        URL.revokeObjectURL(file.preview_url)
      }
    }
    attachedFiles.value = []
  }

  const getFileIds = (): string[] => {
    return attachedFiles.value
      .filter(f => f.status === 'ready' && f.file_id !== null)
      .map(f => f.file_id as string)
  }

  return {
    attachedFiles,
    addFiles,
    removeFile,
    clearFiles,
    allFilesReady,
    getFileIds,
  }
}
