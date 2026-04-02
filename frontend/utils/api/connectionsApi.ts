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
  }
}
