export function createGa4Api(fetchWithRefresh: Function) {
  return {
    async detect(connectionId: number) {
      return fetchWithRefresh(`/api/bigquery/ga4/detect?connection_id=${connectionId}`, {})
    },
    async listConfigs(connectionId: number) {
      return fetchWithRefresh(`/api/bigquery/ga4/configs?connection_id=${connectionId}`, {})
    },
    async upsertConfig(data: {
      connection_id: number
      analytics_dataset_id: string
      tag_name: string
      lookback_days: number
      schedule_time: string
    }) {
      return fetchWithRefresh('/api/bigquery/ga4/configs', {
        method: 'POST',
        body: data,
      })
    },
    async patchConfig(configId: number, data: Record<string, any>) {
      return fetchWithRefresh(`/api/bigquery/ga4/configs/${configId}`, {
        method: 'PATCH',
        body: data,
      })
    },
    async deleteConfig(configId: number) {
      return fetchWithRefresh(`/api/bigquery/ga4/configs/${configId}`, {
        method: 'DELETE',
      })
    },
    async trigger(configId: number) {
      return fetchWithRefresh(`/api/bigquery/ga4/configs/${configId}/trigger`, {
        method: 'POST',
      })
    },
    async discoverParams(data: {
      connection_id: number
      analytics_dataset_id: string
      lookback_days: number
    }) {
      return fetchWithRefresh('/api/bigquery/ga4/discover-params', {
        method: 'POST',
        body: data,
      })
    },
  }
}
