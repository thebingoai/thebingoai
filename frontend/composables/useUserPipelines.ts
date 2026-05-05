import { ref } from 'vue'
import { useApi } from './useApi'

export interface Pipeline {
  id: string
  name: string
  owner_scope_kind: string
  owner_scope_id: string
  source_connection_id: number
  target_table: string
  cron: string | null
  mode: 'full' | 'incremental'
  incremental_key: string | null
  extraction_config: Record<string, unknown>
  pipeline_fingerprint: string
  last_run_at: string | null
  last_run_status: 'success' | 'failed' | 'running' | null
  next_run_at: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface PipelineRun {
  id: string
  pipeline_id: string
  started_at: string
  finished_at: string | null
  status: 'running' | 'success' | 'failed'
  rows_written: number | null
  bytes_written: number | null
  error_message: string | null
  triggered_by: 'cron' | 'manual' | 'api'
}

export interface CreatePipelinePayload {
  name: string
  source_connection_id: number
  owner_scope_kind: string
  owner_scope_id: string
  target_table: string
  cron?: string
  mode: 'full' | 'incremental'
  incremental_key?: string
  extraction_config: Record<string, unknown>
}

export function useUserPipelines() {
  const api = useApi()
  const pipelines = ref<Pipeline[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchPipelines() {
    loading.value = true
    error.value = null
    try {
      const data = await (api as any).fetchWithRefresh('/api/pipelines', {})
      pipelines.value = Array.isArray(data) ? data : []
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load pipelines'
    } finally {
      loading.value = false
    }
  }

  async function createPipeline(payload: CreatePipelinePayload): Promise<Pipeline> {
    const data = await (api as any).fetchWithRefresh('/api/pipelines', {
      method: 'POST',
      body: payload,
    })
    pipelines.value = [...pipelines.value, data]
    return data
  }

  async function triggerRun(pipelineId: string): Promise<{ run_id: string; status: string }> {
    return (api as any).fetchWithRefresh(`/api/pipelines/${pipelineId}/run`, { method: 'POST' })
  }

  async function fetchRuns(pipelineId: string): Promise<PipelineRun[]> {
    return (api as any).fetchWithRefresh(`/api/pipelines/${pipelineId}/runs`, {})
  }

  return { pipelines, loading, error, fetchPipelines, createPipeline, triggerRun, fetchRuns }
}
