export function createDashboardsApi(fetchWithRefresh: Function) {
  return {
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
    async refreshWidget(data: { connection_id: number; sql: string; mapping: any; limit?: number; filters?: Array<{ column: string; op: string; value: any }>; dashboard_id?: number; widget_id?: string; widget_sources?: string[] }) {
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
  }
}
