import { ref } from 'vue'
import { useApi } from './useApi'

export interface Transform {
  id: string
  name: string
  owner_scope_kind: string
  owner_scope_id: string
  sql: string
  materialization: 'table' | 'view' | 'incremental'
  unique_key: string | null
  cron: string | null
  last_run_at: string | null
  last_run_status: 'success' | 'failed' | 'running' | null
  next_run_at: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface TransformRun {
  id: string
  transform_id: string
  started_at: string
  finished_at: string | null
  status: 'running' | 'success' | 'failed'
  error_message: string | null
  triggered_by: 'cron' | 'manual' | 'api'
}

export interface CreateTransformPayload {
  name: string
  sql: string
  materialization: 'table' | 'view' | 'incremental'
  owner_scope_kind: string
  owner_scope_id: string
  cron?: string
  unique_key?: string
}

export function useUserTransforms() {
  const api = useApi()
  const transforms = ref<Transform[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchTransforms() {
    loading.value = true
    error.value = null
    try {
      const data = await (api as any).fetchWithRefresh('/api/transforms', {})
      transforms.value = Array.isArray(data) ? data : []
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load transforms'
    } finally {
      loading.value = false
    }
  }

  async function fetchTransform(transformId: string): Promise<Transform> {
    return (api as any).fetchWithRefresh(`/api/transforms/${transformId}`, {})
  }

  async function createTransform(payload: CreateTransformPayload): Promise<Transform> {
    const data = await (api as any).fetchWithRefresh('/api/transforms', {
      method: 'POST',
      body: payload,
    })
    transforms.value = [...transforms.value, data]
    return data
  }

  async function updateTransform(transformId: string, patch: Partial<Pick<Transform, 'name' | 'sql' | 'materialization' | 'unique_key' | 'cron' | 'enabled'>>): Promise<Transform> {
    const data = await (api as any).fetchWithRefresh(`/api/transforms/${transformId}`, {
      method: 'PATCH',
      body: patch,
    })
    transforms.value = transforms.value.map(t => t.id === transformId ? data : t)
    return data
  }

  async function triggerRun(transformId: string): Promise<{ run_id: string; status: string }> {
    return (api as any).fetchWithRefresh(`/api/transforms/${transformId}/run`, { method: 'POST' })
  }

  async function fetchRuns(transformId: string): Promise<TransformRun[]> {
    return (api as any).fetchWithRefresh(`/api/transforms/${transformId}/runs`, {})
  }

  return { transforms, loading, error, fetchTransforms, fetchTransform, createTransform, updateTransform, triggerRun, fetchRuns }
}
