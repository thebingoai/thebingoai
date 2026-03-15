import { useAuthStore } from '~/stores/auth'

export const useApi = () => {
  const authStore = useAuthStore()
  const router = useRouter()

  const getHeaders = () => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    }

    if (authStore.token) {
      headers['Authorization'] = `Bearer ${authStore.token}`
    }

    return headers
  }

  const fetchWithRefresh = async <T>(url: string, options: Parameters<typeof $fetch>[1] = {}): Promise<T> => {
    try {
      return await $fetch<T>(url, {
        ...options,
        headers: {
          ...getHeaders(),
          ...(options.headers as Record<string, string> || {}),
        },
      })
    } catch (error: any) {
      if (error?.statusCode === 401 || error?.status === 401) {
        const refreshed = await authStore.refreshAccessToken()
        if (refreshed) {
          // Retry with new token
          return await $fetch<T>(url, {
            ...options,
            headers: {
              ...getHeaders(),
              ...(options.headers as Record<string, string> || {}),
            },
          })
        } else {
          // Refresh failed - logout and redirect
          await authStore.logout()
          await router.push('/login')
          throw error
        }
      }
      throw error
    }
  }

  return {
    fetchWithRefresh,
    // Auth endpoints
    auth: {
      async login(email: string, password: string) {
        return authStore.login({ email, password })
      },
      async register(email: string, password: string) {
        return authStore.register(email, password)
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
      },
      async getTypes() {
        return $fetch('/api/connections/types', {
          headers: getHeaders()
        })
      },
      async testUnsaved(data: any) {
        return $fetch('/api/connections/test-connection', {
          method: 'POST',
          headers: getHeaders(),
          body: data
        })
      },
      async getSchema(id: string) {
        return $fetch(`/api/connections/${id}/schema`, {
          headers: getHeaders()
        })
      },
      async listOrg() {
        return $fetch('/api/connections/org', {
          headers: getHeaders()
        })
      },
      async executeQuery(connectionId: string, sql: string, limit?: number) {
        return $fetch(`/api/connections/${connectionId}/query`, {
          method: 'POST',
          headers: getHeaders(),
          body: { sql, limit: limit ?? 100 }
        })
      }
    },

    // Chat endpoints
    chat: {
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
      },
      async updateTitle(threadId: string, title: string) {
        return $fetch(`/api/chat/conversations/${threadId}/title`, {
          method: 'PATCH',
          headers: getHeaders(),
          body: { title }
        })
      },
      async getMessageSteps(threadId: string, messageId: string) {
        return $fetch(`/api/chat/conversations/${threadId}/messages/${messageId}/steps`, {
          headers: getHeaders()
        })
      },
      async uploadChatFiles(files: File[]) {
        return new Promise((resolve, reject) => {
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
                reject(new Error(error.detail || 'Upload failed'))
              } catch (e) {
                reject(new Error(`Upload failed with status ${xhr.status}`))
              }
            }
          })

          xhr.addEventListener('error', () => {
            reject(new Error('Network error during upload'))
          })

          xhr.open('POST', '/api/chat/files/upload')
          if (authStore.token) {
            xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
          }
          xhr.send(formData)
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
      },
      async listEntries(skip?: number, limit?: number) {
        const params = new URLSearchParams()
        if (skip !== undefined) params.append('skip', skip.toString())
        if (limit !== undefined) params.append('limit', limit.toString())
        return $fetch(`/api/memory/entries?${params.toString()}`, {
          headers: getHeaders()
        })
      },
      async createEntry(content: string, category?: string) {
        return $fetch('/api/memory/entries', {
          method: 'POST',
          headers: getHeaders(),
          body: { content, category }
        })
      },
      async updateEntry(id: string, data: { content?: string; category?: string | null; is_active?: boolean }) {
        return $fetch(`/api/memory/entries/${id}`, {
          method: 'PUT',
          headers: getHeaders(),
          body: data
        })
      },
      async deleteEntry(id: string) {
        return $fetch(`/api/memory/entries/${id}`, {
          method: 'DELETE',
          headers: getHeaders()
        })
      },
      async getSettings() {
        return $fetch('/api/memory/settings', {
          headers: getHeaders()
        })
      },
      async updateSettings(memory_enabled: boolean) {
        return $fetch('/api/memory/settings', {
          method: 'PUT',
          headers: getHeaders(),
          body: { memory_enabled }
        })
      },
      async heatmap() {
        return $fetch('/api/memory/heatmap', { headers: getHeaders() })
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
    },

    // Organization endpoints
    orgs: {
      async get(orgId: string) {
        return $fetch(`/api/orgs/${orgId}`, {
          headers: getHeaders()
        })
      },
      async getTeams(orgId: string) {
        return $fetch(`/api/orgs/${orgId}/teams`, {
          headers: getHeaders()
        })
      },
      async createTeam(orgId: string, name: string) {
        return $fetch(`/api/orgs/${orgId}/teams`, {
          method: 'POST',
          headers: getHeaders(),
          body: { name }
        })
      }
    },

    // Team endpoints
    teams: {
      async getMembers(teamId: string) {
        return $fetch(`/api/teams/${teamId}/members`, {
          headers: getHeaders()
        })
      },
      async addMember(teamId: string, userId: string, role: string) {
        return $fetch(`/api/teams/${teamId}/members`, {
          method: 'POST',
          headers: getHeaders(),
          body: { user_id: userId, role }
        })
      },
      async removeMember(teamId: string, userId: string) {
        return $fetch(`/api/teams/${teamId}/members/${userId}`, {
          method: 'DELETE',
          headers: getHeaders()
        })
      },
      async updateMemberRole(teamId: string, userId: string, role: string) {
        return $fetch(`/api/teams/${teamId}/members/${userId}`, {
          method: 'PATCH',
          headers: getHeaders(),
          body: { role }
        })
      }
    },

    // Policy endpoints
    policies: {
      async getToolCatalog() {
        return $fetch('/api/tools/catalog', {
          headers: getHeaders()
        })
      },
      async getToolPolicy(teamId: string) {
        return $fetch(`/api/tools/teams/${teamId}/policies/tools`, {
          headers: getHeaders()
        })
      },
      async setToolPolicy(teamId: string, toolKeys: string[]) {
        return $fetch(`/api/tools/teams/${teamId}/policies/tools`, {
          method: 'PUT',
          headers: getHeaders(),
          body: { tool_keys: toolKeys }
        })
      },
      async getConnectionPolicy(teamId: string) {
        return $fetch(`/api/tools/teams/${teamId}/policies/connections`, {
          headers: getHeaders()
        })
      },
      async setConnectionPolicy(teamId: string, connectionIds: number[]) {
        return $fetch(`/api/tools/teams/${teamId}/policies/connections`, {
          method: 'PUT',
          headers: getHeaders(),
          body: { connection_ids: connectionIds }
        })
      }
    },

    // Skills endpoints
    skills: {
      async list() {
        return $fetch('/api/skills', { headers: getHeaders() })
      },
      async get(id: string) {
        return $fetch(`/api/skills/${id}`, { headers: getHeaders() })
      },
      async listReferences(skillId: string) {
        return $fetch(`/api/skills/${skillId}/references`, { headers: getHeaders() })
      },
      async toggle(id: string, isActive: boolean) {
        return $fetch(`/api/skills/${id}`, {
          method: 'PATCH',
          headers: getHeaders(),
          body: { is_active: isActive }
        })
      },
      async remove(id: string) {
        return $fetch(`/api/skills/${id}`, {
          method: 'DELETE',
          headers: getHeaders()
        })
      },
      async listSuggestions() {
        return $fetch('/api/skills/suggestions', { headers: getHeaders() })
      },
      async respondToSuggestion(id: string, action: 'accept' | 'dismiss') {
        return $fetch(`/api/skills/suggestions/${id}`, {
          method: 'PATCH',
          headers: getHeaders(),
          body: { action }
        })
      }
    },

    // Dashboard endpoints
    dashboards: {
      async list() {
        return $fetch('/api/dashboards', { headers: getHeaders() })
      },
      async get(id: number) {
        return $fetch(`/api/dashboards/${id}`, { headers: getHeaders() })
      },
      async create(data: any) {
        return $fetch('/api/dashboards', {
          method: 'POST',
          headers: getHeaders(),
          body: data,
        })
      },
      async update(id: number, data: any) {
        return $fetch(`/api/dashboards/${id}`, {
          method: 'PUT',
          headers: getHeaders(),
          body: data,
        })
      },
      async delete(id: number) {
        return $fetch(`/api/dashboards/${id}`, {
          method: 'DELETE',
          headers: getHeaders(),
        })
      },
      async refreshWidget(data: { connection_id: number; sql: string; mapping: any; limit?: number; filters?: Array<{ column: string; op: string; value: any }> }) {
        return $fetch('/api/dashboards/widgets/refresh', {
          method: 'POST',
          headers: getHeaders(),
          body: data,
        })
      },
      async refreshAll(dashboardId: number) {
        return $fetch(`/api/dashboards/${dashboardId}/refresh`, {
          method: 'POST',
          headers: getHeaders(),
        })
      },
      async suggestFix(data: { connection_id: number; sql: string; error_message: string; mapping: any; widget_title?: string; widget_description?: string }) {
        return $fetch('/api/dashboards/widgets/suggest-fix', {
          method: 'POST',
          headers: getHeaders(),
          body: data,
        }) as Promise<{ suggested_sql: string; explanation: string }>
      },
      async setSchedule(id: number, data: { schedule_type: string; schedule_value: string }) {
        return $fetch(`/api/dashboards/${id}/schedule`, {
          method: 'PUT',
          headers: getHeaders(),
          body: data,
        })
      },
      async toggleSchedule(id: number, active: boolean) {
        return $fetch(`/api/dashboards/${id}/schedule`, {
          method: 'PATCH',
          headers: getHeaders(),
          body: { schedule_active: active },
        })
      },
      async removeSchedule(id: number) {
        return $fetch(`/api/dashboards/${id}/schedule`, {
          method: 'DELETE',
          headers: getHeaders(),
        })
      },
      async listRefreshRuns(id: number, limit = 20, offset = 0) {
        return $fetch(`/api/dashboards/${id}/schedule/runs?limit=${limit}&offset=${offset}`, {
          headers: getHeaders(),
        })
      },
      async triggerRefresh(id: number) {
        return $fetch(`/api/dashboards/${id}/schedule/run`, {
          method: 'POST',
          headers: getHeaders(),
        })
      },
    },

    // Heartbeat Jobs endpoints
    heartbeatJobs: {
      async list() {
        return $fetch('/api/heartbeat-jobs', { headers: getHeaders() })
      },
      async create(data: any) {
        return $fetch('/api/heartbeat-jobs', {
          method: 'POST',
          headers: getHeaders(),
          body: data
        })
      },
      async get(id: string) {
        return $fetch(`/api/heartbeat-jobs/${id}`, { headers: getHeaders() })
      },
      async update(id: string, data: any) {
        return $fetch(`/api/heartbeat-jobs/${id}`, {
          method: 'PUT',
          headers: getHeaders(),
          body: data
        })
      },
      async toggle(id: string, isActive: boolean) {
        return $fetch(`/api/heartbeat-jobs/${id}`, {
          method: 'PATCH',
          headers: getHeaders(),
          body: { is_active: isActive }
        })
      },
      async remove(id: string) {
        return $fetch(`/api/heartbeat-jobs/${id}`, {
          method: 'DELETE',
          headers: getHeaders()
        })
      },
      async listRuns(id: string, limit = 20, offset = 0) {
        return $fetch(`/api/heartbeat-jobs/${id}/runs?limit=${limit}&offset=${offset}`, {
          headers: getHeaders()
        })
      },
      async triggerRun(id: string) {
        return $fetch(`/api/heartbeat-jobs/${id}/run`, {
          method: 'POST',
          headers: getHeaders()
        })
      }
    }
  }
}

