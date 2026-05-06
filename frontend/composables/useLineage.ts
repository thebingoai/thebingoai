import { ref } from 'vue'
import { useApi } from './useApi'

export interface LineageNode {
  id: string
  kind: 'connection' | 'table' | 'widget'
  name: string
  meta: Record<string, any>
}

export interface LineageEdge {
  src: string
  dst: string
  kind: 'source_to_table' | 'table_to_table' | 'table_to_widget'
}

export interface LineageGraph {
  scope_kind: string
  scope_id: string
  nodes: LineageNode[]
  edges: LineageEdge[]
  incomplete_widgets: string[]
}

export interface LastWrite {
  writer: 'pipeline' | 'dbt'
  run_id: string
  pipeline_id?: string
  model_id?: string
  started_at: string | null
  finished_at: string | null
  status: string
  rows_written?: number | null
}

export function useLineage() {
  const api = useApi() as any
  const fetchWithRefresh = api.fetchWithRefresh

  const graph = ref<LineageGraph | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchGraph(scope_kind?: string, scope_id?: string) {
    loading.value = true
    error.value = null
    try {
      const qs = scope_kind && scope_id ? `?scope_kind=${scope_kind}&scope_id=${scope_id}` : ''
      const res = await fetchWithRefresh(`/api/lineage/graph${qs}`, {}) as LineageGraph
      graph.value = res
      return res
    } catch (e: any) {
      error.value = e?.message || 'Failed to load lineage'
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchTableLineage(table: string, hops = 2) {
    return fetchWithRefresh(`/api/lineage/table/${encodeURIComponent(table)}?hops=${hops}`, {})
  }

  async function fetchDashboardLineage(dashboardId: number, hops = 3) {
    return fetchWithRefresh(`/api/lineage/dashboard/${dashboardId}?hops=${hops}`, {})
  }

  async function fetchConnectionLineage(connectionId: number, hops = 3) {
    return fetchWithRefresh(`/api/lineage/connection/${connectionId}?hops=${hops}`, {})
  }

  async function getLastWrite(table: string): Promise<LastWrite | null> {
    const out: any = await fetchTableLineage(table, 1)
    return (out?.last_write as LastWrite) ?? null
  }

  async function invalidateScope(scope_kind?: string, scope_id?: string) {
    const qs = scope_kind && scope_id ? `?scope_kind=${scope_kind}&scope_id=${scope_id}` : ''
    return fetchWithRefresh(`/api/lineage/invalidate${qs}`, { method: 'POST' })
  }

  return {
    graph,
    loading,
    error,
    fetchGraph,
    fetchTableLineage,
    fetchDashboardLineage,
    fetchConnectionLineage,
    getLastWrite,
    invalidateScope,
  }
}
