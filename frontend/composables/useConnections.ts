// Module-level reactive cache shared across all component instances
const cache = ref<Record<number, { name: string; dbType: string }> | null>(null)
let fetchPromise: Promise<void> | null = null

const DB_TYPE_LABELS: Record<string, string> = {
  postgres: 'PostgreSQL',
  mysql: 'MySQL',
}

export const useConnections = () => {
  const api = useApi()

  const ensureLoaded = async () => {
    if (cache.value !== null) return
    if (fetchPromise) return fetchPromise

    fetchPromise = api.connections.list().then((data: any) => {
      const connections = Array.isArray(data) ? data : (data?.connections ?? [])
      cache.value = Object.fromEntries(
        connections.map((c: any) => [c.id, { name: c.name, dbType: c.db_type ?? '' }])
      )
    }).catch(() => {
      cache.value = {}
    }).finally(() => {
      fetchPromise = null
    })

    return fetchPromise
  }

  const getConnectionLabel = (id: number): string => {
    const entry = cache.value?.[id]
    if (!entry) return `Connection #${id}`
    const typeLabel = DB_TYPE_LABELS[entry.dbType] ?? entry.dbType
    return typeLabel ? `${typeLabel} : ${entry.name}` : entry.name
  }

  return { ensureLoaded, getConnectionLabel }
}
