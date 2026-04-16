import { xhrUpload, withAuthRetry } from './xhrUpload'

export function createConnectionsApi(fetchWithRefresh: Function, authStore: any, router: any) {
  return {
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
    async testWrite(id: string) {
      return fetchWithRefresh(`/api/connections/${id}/test-write`, {
        method: 'POST',
      })
    },
    async testWriteUnsaved(data: any) {
      return fetchWithRefresh('/api/connections/test-connection-write', {
        method: 'POST',
        body: data
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
    async getChangelog(typeId: string) {
      return fetchWithRefresh(`/api/connections/types/${typeId}/changelog`, {})
    },
    async getSchema(id: string) {
      return fetchWithRefresh(`/api/connections/${id}/schema`, {})
    },
    async getProfilingStatus(id: number) {
      return fetchWithRefresh(`/api/connections/${id}/profiling-status`, {})
    },
    async reprofile(id: number) {
      return fetchWithRefresh(`/api/connections/${id}/reprofile`, {
        method: 'POST',
      })
    },
    async getContext(id: number) {
      return fetchWithRefresh(`/api/connections/${id}/context`, {})
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
    async uploadSqlite(file: File, name?: string) {
      const formData = new FormData()
      formData.append('file', file)
      if (name) formData.append('name', name)

      return withAuthRetry(
        (token) => xhrUpload({ url: '/api/connections/upload-sqlite', formData, token }),
        authStore,
        router
      )
    },
    async uploadDataset(file: File, name?: string, onProgress?: (percent: number) => void, threadId?: string | null) {
      const formData = new FormData()
      formData.append('file', file)
      if (name) formData.append('name', name)

      const url = threadId
        ? `/api/connections/upload-dataset?thread_id=${encodeURIComponent(threadId)}`
        : '/api/connections/upload-dataset'

      return withAuthRetry(
        (token) => xhrUpload({ url, formData, token, onProgress }),
        authStore,
        router
      )
    }
  }
}
