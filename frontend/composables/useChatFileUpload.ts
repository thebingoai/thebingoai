export interface FileAttachment {
  file: File
  file_id: string | null
  preview_url: string | null  // object URL for images
  status: 'uploading' | 'ready' | 'error'
  error?: string
}

interface FileRejection {
  name: string
  error: string
}

const MAX_FILE_COUNT = 5
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024 // 10MB

const ACCEPTED_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
  'text/csv',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])

const IMAGE_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
])

// Module-level singleton state (shared across all callers)
const attachedFiles = ref<FileAttachment[]>([])

const allFilesReady = computed<boolean>(() => {
  return attachedFiles.value.length > 0 && attachedFiles.value.every(f => f.status === 'ready')
})

export const useChatFileUpload = () => {
  const api = useApi()

  const addFiles = async (files: File[]): Promise<FileRejection[]> => {
    const rejections: FileRejection[] = []
    const validFiles: File[] = []

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

      if (!ACCEPTED_TYPES.has(file.type)) {
        rejections.push({ name: file.name, error: 'Unsupported file type' })
        continue
      }

      if (file.size > MAX_FILE_SIZE_BYTES) {
        rejections.push({ name: file.name, error: 'File size exceeds 10MB limit' })
        continue
      }

      validFiles.push(file)
    }

    if (validFiles.length === 0) {
      return rejections
    }

    // Build attachment objects with initial status and preview URLs
    const newAttachments: FileAttachment[] = validFiles.map(file => ({
      file,
      file_id: null,
      preview_url: IMAGE_TYPES.has(file.type) ? URL.createObjectURL(file) : null,
      status: 'uploading' as const,
    }))

    // Track the starting index for these new attachments
    const startIndex = attachedFiles.value.length
    attachedFiles.value = [...attachedFiles.value, ...newAttachments]

    // Upload the valid files
    try {
      const chatApi = api.chat as any
      if (typeof chatApi.uploadChatFiles !== 'function') {
        throw new Error('uploadChatFiles API method is not yet available')
      }

      const response = await chatApi.uploadChatFiles(validFiles) as { files: Array<{ file_id: string }> }

      // Update each uploaded file with its file_id and mark as ready
      const updatedAttachments = [...attachedFiles.value]
      response.files.forEach((fileResult, i) => {
        const idx = startIndex + i
        if (updatedAttachments[idx]) {
          updatedAttachments[idx] = {
            ...updatedAttachments[idx],
            file_id: fileResult.file_id,
            status: 'ready',
          }
        }
      })
      attachedFiles.value = updatedAttachments
    } catch (err: any) {
      // Mark all newly added files as errored
      const updatedAttachments = [...attachedFiles.value]
      for (let i = startIndex; i < startIndex + newAttachments.length; i++) {
        updatedAttachments[i] = {
          ...updatedAttachments[i],
          status: 'error',
          error: err?.message || 'Upload failed',
        }
      }
      attachedFiles.value = updatedAttachments
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
