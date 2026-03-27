import { useAuthStore } from '~/stores/auth'
import { useSupabase } from '~/composables/useSupabase'

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
        return fetchWithRefresh('/api/auth/me', {})
      }
    },

    // Connection endpoints
    connections: {
      async list() {
        return fetchWithRefresh('/api/connections', {})
      },
      async get(id: string) {
        return fetchWithRefresh(`/api/connections/${id}`, {})
      },
      async create(data: any) {
        return fetchWithRefresh('/api/connections', {
          method: 'POST',
          body: data
        })
      },
      async update(id: string, data: any) {
        return fetchWithRefresh(`/api/connections/${id}`, {
          method: 'PUT',
          body: data
        })
      },
      async delete(id: string) {
        return fetchWithRefresh(`/api/connections/${id}`, {
          method: 'DELETE',
        })
      },
      async test(id: string) {
        return fetchWithRefresh(`/api/connections/${id}/test`, {
          method: 'POST',
        })
      },
      async refreshSchema(id: string) {
        return fetchWithRefresh(`/api/connections/${id}/refresh-schema`, {
          method: 'POST',
        })
      },
      async getTypes() {
        return fetchWithRefresh('/api/connections/types', {})
      },
      async testUnsaved(data: any) {
        return fetchWithRefresh('/api/connections/test-connection', {
          method: 'POST',
          body: data
        })
      },
      async getSchema(id: string) {
        return fetchWithRefresh(`/api/connections/${id}/schema`, {})
      },
      async listOrg() {
        return fetchWithRefresh('/api/connections/org', {})
      },
      async executeQuery(connectionId: string, sql: string, limit?: number) {
        return fetchWithRefresh(`/api/connections/${connectionId}/query`, {
          method: 'POST',
          body: { sql, limit: limit ?? 100 }
        })
      },
      async uploadDataset(file: File, name?: string) {
        const doUpload = (token: string | null): Promise<any> => new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest()
          const formData = new FormData()
          formData.append('file', file)
          if (name) formData.append('name', name)

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

          xhr.open('POST', '/api/connections/upload-dataset')
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
              await authStore.logout()
              await router.push('/login')
            }
          }
          throw error
        }
      }
    },

    // Chat endpoints
    chat: {
      async getConversations() {
        return fetchWithRefresh('/api/chat/conversations', {})
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
      async getStreamingStatus(threadId: string) {
        return fetchWithRefresh(`/api/chat/conversations/${threadId}/streaming`, {}) as Promise<{ streaming: boolean }>
      },
      async getMessageSteps(threadId: string, messageId: string) {
        return fetchWithRefresh(`/api/chat/conversations/${threadId}/messages/${messageId}/steps`, {})
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
    },

    // Upload endpoints
    upload: {
      async uploadFiles(files: File[], namespace?: string, onProgress?: (percent: number) => void) {
        const doUpload = (token: string | null): Promise<any> => new Promise((resolve, reject) => {
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
                reject(Object.assign(new Error(error.detail || 'Upload failed'), { status: xhr.status }))
              } catch (e) {
                reject(Object.assign(new Error(`Upload failed with status ${xhr.status}`), { status: xhr.status }))
              }
            }
          })

          xhr.addEventListener('error', () => {
            reject(new Error('Network error during upload'))
          })

          xhr.open('POST', '/api/upload')
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
              await authStore.logout()
              await router.push('/login')
            }
          }
          throw error
        }
      }
    },

    // Job endpoints
    jobs: {
      async list() {
        return fetchWithRefresh('/api/jobs', {})
      },
      async get(jobId: string) {
        return fetchWithRefresh(`/api/jobs/${jobId}`, {})
      }
    },

    // Memory endpoints
    memory: {
      async search(query: string, limit?: number) {
        return fetchWithRefresh('/api/memory/search', {
          method: 'POST',
          body: { query, limit }
        })
      },
      async list(skip?: number, limit?: number) {
        const params = new URLSearchParams()
        if (skip) params.append('skip', skip.toString())
        if (limit) params.append('limit', limit.toString())

        return fetchWithRefresh(`/api/memory?${params.toString()}`, {})
      },
      async deleteAll() {
        return fetchWithRefresh('/api/memory', {
          method: 'DELETE',
        })
      },
      async listEntries(skip?: number, limit?: number) {
        const params = new URLSearchParams()
        if (skip !== undefined) params.append('skip', skip.toString())
        if (limit !== undefined) params.append('limit', limit.toString())
        return fetchWithRefresh(`/api/memory/entries?${params.toString()}`, {})
      },
      async createEntry(content: string, category?: string) {
        return fetchWithRefresh('/api/memory/entries', {
          method: 'POST',
          body: { content, category }
        })
      },
      async updateEntry(id: string, data: { content?: string; category?: string | null; is_active?: boolean }) {
        return fetchWithRefresh(`/api/memory/entries/${id}`, {
          method: 'PUT',
          body: data
        })
      },
      async deleteEntry(id: string) {
        return fetchWithRefresh(`/api/memory/entries/${id}`, {
          method: 'DELETE',
        })
      },
      async getSettings() {
        return fetchWithRefresh('/api/memory/settings', {})
      },
      async updateSettings(memory_enabled: boolean) {
        return fetchWithRefresh('/api/memory/settings', {
          method: 'PUT',
          body: { memory_enabled }
        })
      },
      async heatmap() {
        return fetchWithRefresh('/api/memory/heatmap', {})
      }
    },

    // Usage endpoints
    usage: {
      async getSummary(days?: number) {
        const params = days ? `?days=${days}` : ''
        return fetchWithRefresh(`/api/usage/summary${params}`, {})
      },
    },

    // Organization endpoints
    orgs: {
      async get(orgId: string) {
        return fetchWithRefresh(`/api/orgs/${orgId}`, {})
      },
      async getTeams(orgId: string) {
        return fetchWithRefresh(`/api/orgs/${orgId}/teams`, {})
      },
      async createTeam(orgId: string, name: string) {
        return fetchWithRefresh(`/api/orgs/${orgId}/teams`, {
          method: 'POST',
          body: { name }
        })
      }
    },

    // Team endpoints
    teams: {
      async getMembers(teamId: string) {
        return fetchWithRefresh(`/api/teams/${teamId}/members`, {})
      },
      async addMember(teamId: string, userId: string, role: string) {
        return fetchWithRefresh(`/api/teams/${teamId}/members`, {
          method: 'POST',
          body: { user_id: userId, role }
        })
      },
      async removeMember(teamId: string, userId: string) {
        return fetchWithRefresh(`/api/teams/${teamId}/members/${userId}`, {
          method: 'DELETE',
        })
      },
      async updateMemberRole(teamId: string, userId: string, role: string) {
        return fetchWithRefresh(`/api/teams/${teamId}/members/${userId}`, {
          method: 'PATCH',
          body: { role }
        })
      }
    },

    // Policy endpoints
    policies: {
      async getToolCatalog() {
        return fetchWithRefresh('/api/tools/catalog', {})
      },
      async getToolPolicy(teamId: string) {
        return fetchWithRefresh(`/api/tools/teams/${teamId}/policies/tools`, {})
      },
      async setToolPolicy(teamId: string, toolKeys: string[]) {
        return fetchWithRefresh(`/api/tools/teams/${teamId}/policies/tools`, {
          method: 'PUT',
          body: { tool_keys: toolKeys }
        })
      },
      async getConnectionPolicy(teamId: string) {
        return fetchWithRefresh(`/api/tools/teams/${teamId}/policies/connections`, {})
      },
      async setConnectionPolicy(teamId: string, connectionIds: number[]) {
        return fetchWithRefresh(`/api/tools/teams/${teamId}/policies/connections`, {
          method: 'PUT',
          body: { connection_ids: connectionIds }
        })
      }
    },

    // Skills endpoints
    skills: {
      async list() {
        return fetchWithRefresh('/api/skills', {})
      },
      async get(id: string) {
        return fetchWithRefresh(`/api/skills/${id}`, {})
      },
      async listReferences(skillId: string) {
        return fetchWithRefresh(`/api/skills/${skillId}/references`, {})
      },
      async toggle(id: string, isActive: boolean) {
        return fetchWithRefresh(`/api/skills/${id}`, {
          method: 'PATCH',
          body: { is_active: isActive }
        })
      },
      async remove(id: string) {
        return fetchWithRefresh(`/api/skills/${id}`, {
          method: 'DELETE',
        })
      },
      async listSuggestions() {
        return fetchWithRefresh('/api/skills/suggestions', {})
      },
      async respondToSuggestion(id: string, action: 'accept' | 'dismiss') {
        return fetchWithRefresh(`/api/skills/suggestions/${id}`, {
          method: 'PATCH',
          body: { action }
        })
      }
    },

    // Dashboard endpoints
    dashboards: {
      async list() {
        return fetchWithRefresh('/api/dashboards', {})
      },
      async get(id: number) {
        return fetchWithRefresh(`/api/dashboards/${id}`, {})
      },
      async create(data: any) {
        return fetchWithRefresh('/api/dashboards', {
          method: 'POST',
          body: data,
        })
      },
      async update(id: number, data: any) {
        return fetchWithRefresh(`/api/dashboards/${id}`, {
          method: 'PUT',
          body: data,
        })
      },
      async delete(id: number) {
        return fetchWithRefresh(`/api/dashboards/${id}`, {
          method: 'DELETE',
        })
      },
      async refreshWidget(data: { connection_id: number; sql: string; mapping: any; limit?: number; filters?: Array<{ column: string; op: string; value: any }> }) {
        return fetchWithRefresh('/api/dashboards/widgets/refresh', {
          method: 'POST',
          body: data,
        })
      },
      async refreshAll(dashboardId: number) {
        return fetchWithRefresh(`/api/dashboards/${dashboardId}/refresh`, {
          method: 'POST',
        })
      },
      async suggestFix(data: { connection_id: number; sql: string; error_message: string; mapping: any; widget_title?: string; widget_description?: string }) {
        return fetchWithRefresh('/api/dashboards/widgets/suggest-fix', {
          method: 'POST',
          body: data,
        }) as Promise<{ suggested_sql: string; explanation: string }>
      },
      async setSchedule(id: number, data: { schedule_type: string; schedule_value: string }) {
        return fetchWithRefresh(`/api/dashboards/${id}/schedule`, {
          method: 'PUT',
          body: data,
        })
      },
      async toggleSchedule(id: number, active: boolean) {
        return fetchWithRefresh(`/api/dashboards/${id}/schedule`, {
          method: 'PATCH',
          body: { schedule_active: active },
        })
      },
      async removeSchedule(id: number) {
        return fetchWithRefresh(`/api/dashboards/${id}/schedule`, {
          method: 'DELETE',
        })
      },
      async listRefreshRuns(id: number, limit = 20, offset = 0) {
        return fetchWithRefresh(`/api/dashboards/${id}/schedule/runs?limit=${limit}&offset=${offset}`, {})
      },
      async triggerRefresh(id: number) {
        return fetchWithRefresh(`/api/dashboards/${id}/schedule/run`, {
          method: 'POST',
        })
      },
      async getSqliteUrl(connectionId: number) {
        return fetchWithRefresh(`/api/connections/datasets/${connectionId}/sqlite-url`, {}) as Promise<{ url: string; expires_in: number }>
      },
    },

    // Terms & Conditions endpoints (enterprise)
    tos: {
      async status() {
        return fetchWithRefresh('/api/tos/status', {})
      },
      async accept(version?: string) {
        return fetchWithRefresh('/api/tos/accept', {
          method: 'POST',
          body: { version: version || '1.0' },
        })
      },
      async content() {
        return fetchWithRefresh('/api/tos/content', {})
      },
    },


    // Heartbeat Jobs endpoints
    heartbeatJobs: {
      async list() {
        return fetchWithRefresh('/api/heartbeat-jobs', {})
      },
      async create(data: any) {
        return fetchWithRefresh('/api/heartbeat-jobs', {
          method: 'POST',
          body: data
        })
      },
      async get(id: string) {
        return fetchWithRefresh(`/api/heartbeat-jobs/${id}`, {})
      },
      async update(id: string, data: any) {
        return fetchWithRefresh(`/api/heartbeat-jobs/${id}`, {
          method: 'PUT',
          body: data
        })
      },
      async toggle(id: string, isActive: boolean) {
        return fetchWithRefresh(`/api/heartbeat-jobs/${id}`, {
          method: 'PATCH',
          body: { is_active: isActive }
        })
      },
      async remove(id: string) {
        return fetchWithRefresh(`/api/heartbeat-jobs/${id}`, {
          method: 'DELETE',
        })
      },
      async listRuns(id: string, limit = 20, offset = 0) {
        return fetchWithRefresh(`/api/heartbeat-jobs/${id}/runs?limit=${limit}&offset=${offset}`, {})
      },
      async triggerRun(id: string) {
        return fetchWithRefresh(`/api/heartbeat-jobs/${id}/run`, {
          method: 'POST',
        })
      }
    }
  }
}

