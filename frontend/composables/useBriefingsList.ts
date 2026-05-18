// Shared, cached briefings list. Survives tab unmount so reopening the
// Briefings tab serves cached data instantly and revalidates in the background.

import type { BriefingResponse } from './useBriefing'

export function useBriefingsList() {
  const { fetchWithRefresh } = useApi()

  const briefings = useState<BriefingResponse[]>('briefings-list', () => [])
  const loaded = useState<boolean>('briefings-list-loaded', () => false)
  const loading = useState<boolean>('briefings-list-loading', () => false)
  const error = useState<string>('briefings-list-error', () => '')
  const inflight = useState<Promise<void> | null>('briefings-list-inflight', () => null)

  async function refresh(): Promise<void> {
    if (inflight.value) return inflight.value
    loading.value = true
    const p = (async () => {
      try {
        const data = (await fetchWithRefresh('/api/briefings?limit=50', { method: 'GET' })) as BriefingResponse[]
        briefings.value = data || []
        loaded.value = true
        error.value = ''
      } catch (e: any) {
        error.value = e?.message || 'Failed to load briefings'
      } finally {
        loading.value = false
        inflight.value = null
      }
    })()
    inflight.value = p
    return p
  }

  function ensure(): void {
    if (loaded.value || inflight.value) return
    refresh()
  }

  function invalidate(): void {
    loaded.value = false
  }

  return { briefings, loaded, loading, error, refresh, ensure, invalidate }
}
