// Module-level reactive cache shared across all component instances
const cache = ref<Record<number, { name: string; dbType: string }> | null>(null)
let fetchPromise: Promise<void> | null = null

// Dynamic type labels populated from /api/connections/types
const typeLabels = ref<Record<string, string>>({})
let typesFetched = false

export const useConnections = () => {
  const api = useApi()

  const ensureLoaded = async () => {
    if (cache.value !== null) return
    if (fetchPromise) return fetchPromise

    fetchPromise = Promise.all([
      api.connections.list(),
      !typesFetched ? api.connections.getTypes().catch(() => []) : Promise.resolve(null),
    ]).then(([data, types]: [any, any]) => {
      const connections = Array.isArray(data) ? data : (data?.connections ?? [])
      cache.value = Object.fromEntries(
        connections.map((c: any) => [c.id, { name: c.name, dbType: c.db_type ?? '' }])
      )
      if (types) {
        typesFetched = true
        for (const t of types) {
          typeLabels.value[t.id] = t.display_name
        }
      }
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
    const label = typeLabels.value[entry.dbType] ?? entry.dbType
    return label ? `${label} : ${entry.name}` : entry.name
  }

  return { ensureLoaded, getConnectionLabel }
}
