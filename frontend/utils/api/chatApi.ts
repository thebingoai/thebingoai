export function createChatApi(fetchWithRefresh: Function, authStore: any, router: any) {
  return {
    async getConversations(archived = false, summary = true) {
      const params = new URLSearchParams()
      if (archived) params.set('archived', 'true')
      if (summary) params.set('summary', 'true')
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
    async uploadChatFiles(files: File[]) {
      const doUpload = (token: string | null): Promise<any> => new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        const formData = new FormData()

        files.forEach(file => formData.append('files', file))

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
              reject(Object.assign(new Error(error.detail || 'Upload failed'), { status: xhr.status }))
            } catch (e) {
              reject(Object.assign(new Error(`Upload failed with status ${xhr.status}`), { status: xhr.status }))
            }
          }
        })

        xhr.addEventListener('error', () => {
          reject(new Error('Network error during upload'))
        })

        xhr.open('POST', '/api/chat/files/upload')
        if (token) {
          xhr.setRequestHeader('Authorization', `Bearer ${token}`)
        }
        xhr.send(formData)
      })

      try {
        return await doUpload(authStore.token)
      } catch (error: any) {
        if (error?.status === 401) {
          const refreshed = await authStore.refreshAccessToken()
          if (refreshed) {
            return await doUpload(authStore.token)
          } else {
            const router = useRouter()
            await authStore.logout()
            await router.push('/login')
          }
        }
        throw error
      }
    }
  }
}
