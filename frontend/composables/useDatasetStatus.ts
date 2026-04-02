import { useChatStore } from '~/stores/chat'
import type { AgentStep } from '~/stores/chat'

export interface DatasetStatus {
  name: string
  size: number
  fileId: string | null
  connectionId: number | null
  step: 'uploading' | 'schema' | 'profiling' | 'ready' | 'failed'
  uploadedAt: string | null
  schemaBuiltAt: string | null
  profilingStartedAt: string | null
  completedAt: string | null
  rowCount: number | null
  columnCount: number | null
  error: string | null
}

const CSV_MIME_TYPES = new Set([
  'text/csv',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
])

const POLL_INTERVAL_MS = 3000

/** Extract ISO timestamp from an agent step (live streaming uses epoch ms, historical uses ISO string). */
function stepTimestamp(step: AgentStep): string | null {
  if (step.created_at) return step.created_at
  if (step.started_at) return new Date(step.started_at).toISOString()
  return null
}

/**
 * Composable that derives per-dataset processing status by joining
 * message attachments, agent steps, and profiling status polling.
 */
export const useDatasetStatus = () => {
  const chatStore = useChatStore()
  const api = useApi()

  // Profiling status cache keyed by connection_id
  const profilingStatuses = ref<Map<number, { status: string; error: string | null; completedAt: string | null }>>(new Map())
  // Non-reactive bookkeeping — interval IDs don't need Vue reactivity
  const pollers: Record<number, ReturnType<typeof setInterval>> = {}

  // --- Polling ---

  async function fetchProfilingStatus(connectionId: number) {
    try {
      const result = await api.connections.getProfilingStatus(connectionId) as {
        profiling_status: string
        profiling_progress: string | null
        profiling_error: string | null
        completed_at: string | null
      }

      profilingStatuses.value.set(connectionId, {
        status: result.profiling_status,
        error: result.profiling_error,
        completedAt: result.completed_at,
      })
      // Trigger reactivity
      profilingStatuses.value = new Map(profilingStatuses.value)

      if (result.profiling_status === 'ready' || result.profiling_status === 'failed') {
        stopPolling(connectionId)
      }
    } catch {
      // Silently ignore polling errors
    }
  }

  async function startPolling(connectionId: number) {
    if (pollers[connectionId]) return

    // Fetch immediately so historical datasets don't flash "profiling" for 3 seconds
    await fetchProfilingStatus(connectionId)
    const cached = profilingStatuses.value.get(connectionId)
    if (cached?.status === 'ready' || cached?.status === 'failed') return

    pollers[connectionId] = setInterval(() => fetchProfilingStatus(connectionId), POLL_INTERVAL_MS)
  }

  function stopPolling(connectionId: number) {
    if (pollers[connectionId]) {
      clearInterval(pollers[connectionId])
      delete pollers[connectionId]
    }
  }

  function stopAllPolling() {
    for (const id of Object.keys(pollers)) {
      clearInterval(pollers[Number(id)])
      delete pollers[Number(id)]
    }
  }

  // --- Core computed ---

  const datasets = computed<DatasetStatus[]>(() => {
    const results: DatasetStatus[] = []

    // Collect all agent steps across messages for lookup
    const allSteps: AgentStep[] = []
    for (const msg of chatStore.messages) {
      if (msg.agent_steps?.length) {
        allSteps.push(...msg.agent_steps)
      }
    }

    // Find create_dataset_from_upload tool calls
    const datasetToolCalls = allSteps.filter(
      s => s.tool_name === 'create_dataset_from_upload' && s.step_type === 'tool_call'
    )

    for (const msg of chatStore.messages) {
      if (!msg.attachments?.length) continue

      for (const att of msg.attachments) {
        // Only show CSV/Excel files in the dataset timeline
        if (!CSV_MIME_TYPES.has(att.type)) continue

        const ds: DatasetStatus = {
          name: att.name,
          size: att.size,
          fileId: att.file_id,
          connectionId: null,
          step: 'uploading',
          uploadedAt: null,
          schemaBuiltAt: null,
          profilingStartedAt: null,
          completedAt: null,
          rowCount: null,
          columnCount: null,
          error: null,
        }

        // Step 1: Upload status
        if (att.status === 'uploading') {
          ds.step = 'uploading'
          ds.uploadedAt = msg.created_at
          results.push(ds)
          continue
        }

        if (att.status === 'error') {
          ds.step = 'failed'
          ds.uploadedAt = msg.created_at
          ds.error = 'Upload failed'
          results.push(ds)
          continue
        }

        // File is uploaded (status === 'ready')
        ds.uploadedAt = msg.created_at

        // Step 2: Find the matching tool call for this file_id
        const toolCall = att.file_id
          ? datasetToolCalls.find(s => s.content?.args?.file_id === att.file_id)
          : null

        if (!toolCall) {
          // Agent hasn't called create_dataset_from_upload yet — could be still
          // processing or file was uploaded but not used for a dataset
          // If streaming is active, show as "uploading" complete, waiting for schema
          if (chatStore.isStreaming) {
            ds.step = 'schema'
            ds.schemaBuiltAt = null
          } else {
            // Not streaming, no tool call — just a plain file, show compact
            ds.step = 'ready'
            ds.completedAt = msg.created_at
          }
          results.push(ds)
          continue
        }

        // Tool call exists — check if it's completed
        if (toolCall.status === 'started') {
          // Schema building in progress
          ds.step = 'schema'
          ds.schemaBuiltAt = null
          results.push(ds)
          continue
        }

        // Tool call completed — extract result
        const result = typeof toolCall.content?.result === 'string'
          ? (() => { try { return JSON.parse(toolCall.content.result) } catch { return toolCall.content.result } })()
          : toolCall.content?.result

        if (result && !result.success) {
          // Dataset creation failed
          ds.step = 'failed'
          ds.schemaBuiltAt = stepTimestamp(toolCall)
          ds.error = result.message || 'Dataset creation failed'
          results.push(ds)
          continue
        }

        // Schema built successfully
        ds.schemaBuiltAt = stepTimestamp(toolCall)
        ds.connectionId = result?.connection_id ?? null
        ds.rowCount = result?.row_count ?? null
        ds.columnCount = result?.columns?.length ?? null

        if (!ds.connectionId) {
          ds.step = 'ready'
          ds.completedAt = ds.schemaBuiltAt
          results.push(ds)
          continue
        }

        // Step 3: Check profiling status
        const profiling = profilingStatuses.value.get(ds.connectionId)

        if (!profiling) {
          // Haven't polled yet — assume profiling is pending
          ds.step = 'profiling'
          ds.profilingStartedAt = ds.schemaBuiltAt
          results.push(ds)
          continue
        }

        if (profiling.status === 'ready') {
          ds.step = 'ready'
          ds.completedAt = profiling.completedAt
          ds.profilingStartedAt = ds.schemaBuiltAt
          results.push(ds)
          continue
        }

        if (profiling.status === 'failed') {
          ds.step = 'failed'
          ds.profilingStartedAt = ds.schemaBuiltAt
          ds.error = profiling.error || 'Profiling failed'
          results.push(ds)
          continue
        }

        // pending or in_progress
        ds.step = 'profiling'
        ds.profilingStartedAt = ds.schemaBuiltAt
        results.push(ds)
      }
    }

    return results
  })

  // --- Watch for new connection IDs to poll ---

  watch(
    () => datasets.value.filter(d => d.connectionId && (d.step === 'profiling')).map(d => d.connectionId!),
    (connectionIds) => {
      for (const id of connectionIds) {
        startPolling(id)
      }
    },
    { immediate: true }
  )

  // Stop all polling when conversation changes
  watch(() => chatStore.currentThreadId, () => {
    stopAllPolling()
    profilingStatuses.value = new Map()
  })

  // Cleanup on unmount
  onUnmounted(() => {
    stopAllPolling()
  })

  // --- Actions ---

  async function retryProfiling(connectionId: number) {
    try {
      await api.connections.reprofile(connectionId)
      profilingStatuses.value.set(connectionId, { status: 'pending', error: null, completedAt: null })
      profilingStatuses.value = new Map(profilingStatuses.value)
      startPolling(connectionId)
    } catch {
      // Silently fail — user can try again
    }
  }

  return {
    datasets,
    retryProfiling,
  }
}
