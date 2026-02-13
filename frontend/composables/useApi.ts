import { useAuthStore } from '~/stores/auth'

export const useApi = () => {
  const authStore = useAuthStore()

  const getHeaders = () => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    }

    if (authStore.token) {
      headers['Authorization'] = `Bearer ${authStore.token}`
    }

    return headers
  }

  return {
    // Auth endpoints
    auth: {
      async login(email: string, password: string) {
        return authStore.login({ email, password })
      },
      async register(email: string, password: string) {
        return authStore.register({ email, password })
      },
      async logout() {
        authStore.logout()
      },
      async me() {
        return $fetch('/api/auth/me', {
          headers: getHeaders()
        })
      }
    },

    // Connection endpoints
    connections: {
      async list() {
        return $fetch('/api/connections', {
          headers: getHeaders()
        })
      },
      async get(id: string) {
        return $fetch(`/api/connections/${id}`, {
          headers: getHeaders()
        })
      },
      async create(data: any) {
        return $fetch('/api/connections', {
          method: 'POST',
          headers: getHeaders(),
          body: data
        })
      },
      async update(id: string, data: any) {
        return $fetch(`/api/connections/${id}`, {
          method: 'PUT',
          headers: getHeaders(),
          body: data
        })
      },
      async delete(id: string) {
        return $fetch(`/api/connections/${id}`, {
          method: 'DELETE',
          headers: getHeaders()
        })
      },
      async test(id: string) {
        return $fetch(`/api/connections/${id}/test`, {
          method: 'POST',
          headers: getHeaders()
        })
      },
      async refreshSchema(id: string) {
        return $fetch(`/api/connections/${id}/refresh-schema`, {
          method: 'POST',
          headers: getHeaders()
        })
      }
    },

    // Chat endpoints
    chat: {
      async send(message: string, threadId?: string, attachments?: File[]) {
        return $fetch('/api/chat', {
          method: 'POST',
          headers: getHeaders(),
          body: {
            message,
            thread_id: threadId,
            connection_ids: []
          }
        })
      },
      async getConversations() {
        return $fetch('/api/chat/conversations', {
          headers: getHeaders()
        })
      },
      async getMessages(threadId: string) {
        return $fetch(`/api/chat/conversations/${threadId}`, {
          headers: getHeaders()
        })
      },
      async deleteConversation(threadId: string) {
        return $fetch(`/api/chat/conversations/${threadId}`, {
          method: 'DELETE',
          headers: getHeaders()
        })
      }
    },

    // Upload endpoints
    upload: {
      async uploadFiles(files: File[], namespace?: string, onProgress?: (percent: number) => void) {
        return new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest()
          const formData = new FormData()

          files.forEach(file => formData.append('files', file))
          if (namespace) formData.append('namespace', namespace)

          if (onProgress) {
            xhr.upload.addEventListener('progress', (e) => {
              if (e.lengthComputable) {
                onProgress(Math.round((e.loaded / e.total) * 100))
              }
            })
          }

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

          xhr.open('POST', '/api/upload')
          if (authStore.token) {
            xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
          }
          xhr.send(formData)
        })
      }
    },

    // Job endpoints
    jobs: {
      async list() {
        return $fetch('/api/jobs', {
          headers: getHeaders()
        })
      },
      async get(jobId: string) {
        return $fetch(`/api/jobs/${jobId}`, {
          headers: getHeaders()
        })
      }
    },

    // Memory endpoints
    memory: {
      async search(query: string, limit?: number) {
        return $fetch('/api/memory/search', {
          method: 'POST',
          headers: getHeaders(),
          body: { query, limit }
        })
      },
      async list(skip?: number, limit?: number) {
        const params = new URLSearchParams()
        if (skip) params.append('skip', skip.toString())
        if (limit) params.append('limit', limit.toString())

        return $fetch(`/api/memory?${params.toString()}`, {
          headers: getHeaders()
        })
      },
      async deleteAll() {
        return $fetch('/api/memory', {
          method: 'DELETE',
          headers: getHeaders()
        })
      }
    },

    // Usage endpoints
    usage: {
      async getStats(period?: number) {
        const params = period ? `?period=${period}` : ''
        return $fetch(`/api/usage/stats${params}`, {
          headers: getHeaders()
        })
      },
      async getOperations(skip?: number, limit?: number) {
        const params = new URLSearchParams()
        if (skip) params.append('skip', skip.toString())
        if (limit) params.append('limit', limit.toString())

        return $fetch(`/api/usage/operations?${params.toString()}`, {
          headers: getHeaders()
        })
      }
    }
  }
}

