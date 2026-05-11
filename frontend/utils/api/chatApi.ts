import { xhrUpload, withAuthRetry } from './xhrUpload'

export function createChatApi(fetchWithRefresh: Function, authStore: any, router: any) {
  return {
    async getConversations(archived = false, summary = true, offset = 0, limit = 199) {
      const params = new URLSearchParams()
      if (archived) params.set('archived', 'true')
      if (summary) params.set('summary', 'true')
      if (offset > 0) params.set('offset', String(offset))
      if (limit !== 199) params.set('limit', String(limit))
      const qs = params.toString()
      return fetchWithRefresh(`/api/chat/conversations${qs ? `?${qs}` : ''}`, {})
    },
    async getMessages(threadId: string) {
      return fetchWithRefresh(`/api/chat/conversations/${threadId}`, {})
    },
    async deleteConversation(threadId: string) {
      return fetchWithRefresh(`/api/chat/conversations/${threadId}`, {
        method: 'DELETE',
      })
    },
    async updateTitle(threadId: string, title: string) {
      return fetchWithRefresh(`/api/chat/conversations/${threadId}/title`, {
        method: 'PATCH',
        body: { title }
      })
    },
    async archiveConversation(threadId: string, archived: boolean) {
      return fetchWithRefresh(`/api/chat/conversations/${threadId}/archive`, {
        method: 'PATCH',
        body: { archived }
      })
    },
    async getStreamingStatus(threadId: string) {
      return fetchWithRefresh(`/api/chat/conversations/${threadId}/streaming`, {}) as Promise<{ streaming: boolean }>
    },
    async getMessageSteps(threadId: string, messageId: string) {
      return fetchWithRefresh(`/api/chat/conversations/${threadId}/messages/${messageId}/steps`, {})
    },
    async getConversationSummary(threadId: string) {
      return fetchWithRefresh(`/api/chat/conversations/${threadId}/summary`, {})
    },
    async generateConversationSummary(threadId: string) {
      return fetchWithRefresh(`/api/chat/conversations/${threadId}/summary/generate`, {
        method: 'POST'
      })
    },
    async getFileUrl(fileId: string, storageKey?: string) {
      const params = storageKey ? `?storage_key=${encodeURIComponent(storageKey)}` : ''
      return fetchWithRefresh(`/api/chat/files/${fileId}/url${params}`, {})
    },
    async uploadChatFiles(files: File[], onProgress?: (percent: number) => void, threadId?: string | null) {
      const formData = new FormData()
      files.forEach(file => formData.append('files', file))

      const url = threadId
        ? `/api/chat/files/upload?thread_id=${encodeURIComponent(threadId)}`
        : '/api/chat/files/upload'

      return withAuthRetry(
        (token) => xhrUpload({ url, formData, token, onProgress }),
        authStore,
        router
      )
    },
    async createConversation() {
      return fetchWithRefresh('/api/chat/conversations/create', {
        method: 'POST',
      })
    },
    async cancelDataset(fileId: string) {
      return fetchWithRefresh(`/api/chat/files/${fileId}/dataset`, {
        method: 'DELETE',
      })
    },
    async getConversationDatasets(threadId: string) {
      return fetchWithRefresh(`/api/chat/conversations/${threadId}/datasets`, {})
    }
  }
}
