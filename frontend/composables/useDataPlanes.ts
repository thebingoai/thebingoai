import { ref, computed } from 'vue'
import { useApi } from './useApi'

export interface DataPlane {
  id: string
  owner_scope_kind: string
  owner_scope_id: string
  type: 'local_filesystem' | 'google_cloud_project'
  config: Record<string, unknown>
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface CreateDataPlanePayload {
  owner_scope_kind: string
  owner_scope_id: string
  type: 'local_filesystem' | 'google_cloud_project'
  config: Record<string, unknown>
  credentials?: string
  is_default: boolean
}

export function useDataPlanes() {
  const { api } = useApi()
  const planes = ref<DataPlane[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchPlanes(orgId: string) {
    loading.value = true
    error.value = null
    try {
      const data = await api<DataPlane[]>(`/api/data-planes?org_id=${encodeURIComponent(orgId)}`)
      planes.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load data planes'
    } finally {
      loading.value = false
    }
  }

  async function createPlane(payload: CreateDataPlanePayload): Promise<DataPlane> {
    const data = await api<DataPlane>('/api/data-planes', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    planes.value = [...planes.value, data]
    return data
  }

  async function updatePlane(id: string, payload: Partial<CreateDataPlanePayload>): Promise<DataPlane> {
    const data = await api<DataPlane>(`/api/data-planes/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    planes.value = planes.value.map(p => p.id === id ? data : p)
    return data
  }

  async function deletePlane(id: string): Promise<void> {
    await api<void>(`/api/data-planes/${id}`, { method: 'DELETE' })
    planes.value = planes.value.filter(p => p.id !== id)
  }

  async function setDefault(id: string): Promise<void> {
    await updatePlane(id, { is_default: true })
    planes.value = planes.value.map(p => ({ ...p, is_default: p.id === id }))
  }

  const defaultPlane = computed(() => planes.value.find(p => p.is_default) ?? null)

  return { planes, loading, error, fetchPlanes, createPlane, updatePlane, deletePlane, setDefault, defaultPlane }
}
