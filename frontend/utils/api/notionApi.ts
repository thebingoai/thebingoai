export function createNotionApi(fetchWithRefresh: Function) {
  return {
    async connect(name: string, apiKey: string): Promise<{ connection_id: number; message: string }> {
      return fetchWithRefresh('/api/notion/connect', {
        method: 'POST',
        body: { connection_name: name, api_key: apiKey },
      })
    },
    async triggerSync(connectionId: number): Promise<{ job_id: string; connection_id: number }> {
      return fetchWithRefresh(`/api/notion/sync/${connectionId}`, { method: 'POST' })
    },
    async listPages(connectionId: number): Promise<{ pages: { id: string; title: string; url: string }[]; synced: boolean; synced_page_count: number }> {
      return fetchWithRefresh(`/api/notion/pages/${connectionId}`)
    },
  }
}
