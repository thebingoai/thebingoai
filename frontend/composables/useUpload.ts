import type { UploadProgress } from '~/types'
import { toast } from 'vue-sonner'
import { MESSAGES } from '~/utils/constants'

export const useUpload = () => {
  const api = useApi()

  const uploads = ref<Map<string, UploadProgress>>(new Map())

  const uploadFile = async (
    file: File,
    namespace: string = 'default',
    tags: string = ''
  ): Promise<string | undefined> => {
    const uploadId = `${Date.now()}-${file.name}`

    const uploadProgress: UploadProgress = {
      id: uploadId,
      file,
      progress: 0,
      status: 'pending'
    }

    uploads.value.set(uploadId, uploadProgress)

    try {
      uploadProgress.status = 'uploading'

      const response = await api.uploadFile(
        file,
        namespace,
        tags,
        (percent) => {
          uploadProgress.progress = percent
          uploads.value.set(uploadId, { ...uploadProgress })
        }
      )

      if (response.status === 'queued') {
        uploadProgress.status = 'processing'
        uploadProgress.job_id = response.job_id
        toast.success(MESSAGES.UPLOAD_QUEUED)
      } else {
        uploadProgress.status = 'completed'
        uploadProgress.progress = 100
        toast.success(MESSAGES.UPLOAD_SUCCESS)
      }

      uploads.value.set(uploadId, { ...uploadProgress })

      return response.job_id
    } catch (err: any) {
      uploadProgress.status = 'failed'
      const errorMessage = err.message || MESSAGES.UPLOAD_ERROR
      uploadProgress.error = errorMessage
      uploads.value.set(uploadId, { ...uploadProgress })
      toast.error(errorMessage)
      throw err
    }
  }

  const uploadMultiple = async (
    files: File[],
    namespace: string = 'default',
    tags: string = ''
  ): Promise<Array<string | undefined>> => {
    return Promise.all(
      files.map(file => uploadFile(file, namespace, tags))
    )
  }

  const removeUpload = (uploadId: string) => {
    uploads.value.delete(uploadId)
  }

  const clearCompleted = () => {
    for (const [id, upload] of uploads.value.entries()) {
      if (upload.status === 'completed' || upload.status === 'failed') {
        uploads.value.delete(id)
      }
    }
  }

  return {
    uploads: readonly(uploads),
    uploadFile,
    uploadMultiple,
    removeUpload,
    clearCompleted
  }
}
