import type {
  UploadResponse,
  QueryRequest,
  QueryResponse,
  AskRequest,
  AskResponse,
  ProvidersResponse,
  ConversationHistoryResponse,
  DeleteConversationResponse,
  StatusResponse,
  DetailedHealthResponse,
  JobInfo,
  JobListResponse
} from '~/types'

export const useApi = () => {
  const config = useRuntimeConfig()
  const settings = useSettingsStore()

  const baseURL = computed(() => settings.backendUrl || config.public.apiBaseUrl)

  // Generic fetch wrapper with error handling
  const apiFetch = async <T>(url: string, options?: any): Promise<T> => {
    try {
      return await $fetch<T>(url, {
        baseURL: baseURL.value,
        ...options
      })
    } catch (error: any) {
      const message = error.data?.detail || error.message || 'An unexpected error occurred'
      throw new Error(message)
    }
  }

  return {
    // Health
    getHealth: () => apiFetch<{ status: string }>('/health'),

    getDetailedHealth: () => apiFetch<DetailedHealthResponse>('/health/detailed'),

    // Status
    getStatus: () => apiFetch<StatusResponse>('/api/status'),

    // Upload
    uploadFile: async (
      file: File,
      namespace: string = 'default',
      tags: string = '',
      onProgress?: (percent: number) => void
    ): Promise<UploadResponse> => {
      // Use XMLHttpRequest for upload progress tracking
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        const formData = new FormData()

        formData.append('file', file)
        formData.append('namespace', namespace)
        if (tags) formData.append('tags', tags)

        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable && onProgress) {
            onProgress(Math.round((e.loaded / e.total) * 100))
          }
        })

        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              resolve(JSON.parse(xhr.responseText))
            } catch (e) {
              reject(new Error('Failed to parse response'))
            }
          } else {
            try {
              const error = JSON.parse(xhr.responseText)
              reject(new Error(error.detail || 'Upload failed'))
            } catch (e) {
              reject(new Error(`Upload failed with status ${xhr.status}`))
            }
          }
        })

        xhr.addEventListener('error', () => {
          reject(new Error('Network error during upload'))
        })

        xhr.open('POST', `${baseURL.value}/api/upload`)
        xhr.send(formData)
      })
    },

    // Query
    query: (request: QueryRequest) =>
      apiFetch<QueryResponse>('/api/query', {
        method: 'POST',
        body: request
      }),

    search: (q: string, namespace?: string, limit?: number) => {
      const params = new URLSearchParams({ q })
      if (namespace) params.append('namespace', namespace)
      if (limit) params.append('limit', limit.toString())
      return apiFetch<QueryResponse>(`/api/search?${params}`)
    },

    // Chat (non-streaming)
    ask: (request: AskRequest) =>
      apiFetch<AskResponse>('/api/ask', {
        method: 'POST',
        body: { ...request, stream: false }
      }),

    // Providers
    getProviders: () => apiFetch<ProvidersResponse>('/api/providers'),

    // Conversations
    getConversation: (threadId: string) =>
      apiFetch<ConversationHistoryResponse>(`/api/conversation/${threadId}`),

    deleteConversation: (threadId: string) =>
      apiFetch<DeleteConversationResponse>(`/api/conversation/${threadId}`, {
        method: 'DELETE'
      }),

    // Jobs
    getJobs: (namespace?: string, limit: number = 50) => {
      const params = new URLSearchParams({ limit: limit.toString() })
      if (namespace) params.append('namespace', namespace)
      return apiFetch<JobListResponse>(`/api/jobs?${params}`)
    },

    getJob: (jobId: string) => apiFetch<JobInfo>(`/api/jobs/${jobId}`)
  }
}
