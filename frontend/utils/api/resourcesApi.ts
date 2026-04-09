import { xhrUpload, withAuthRetry } from './xhrUpload'

export function createResourcesApi(fetchWithRefresh: Function, authStore: any, router: any) {
  return {
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

    // Upload endpoints
    upload: {
      async uploadFiles(files: File[], namespace?: string, onProgress?: (percent: number) => void) {
        const formData = new FormData()
        files.forEach(file => formData.append('files', file))
        if (namespace) formData.append('namespace', namespace)

        return withAuthRetry(
          (token) => xhrUpload({ url: '/api/upload', formData, token, onProgress }),
          authStore,
          router
        )
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
