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
export interface WsDatasetEvent {
  file_id: string
  thread_id: string
  step: 'schema' | 'profiling' | 'ready' | 'failed' | 'cancelled'
  connection_id?: number
  error?: string
}

export const useDatasetStatus = () => {
  const chatStore = useChatStore()
  const api = useApi()
  const ws = useWebSocket()

  // Profiling status cache keyed by connection_id
  const profilingStatuses = ref<Map<number, { status: string; error: string | null; completedAt: string | null }>>(new Map())
  // WebSocket-driven dataset status keyed by file_id
  const wsDatasets = ref<Map<string, WsDatasetEvent>>(new Map())
  // Non-reactive bookkeeping — interval IDs don't need Vue reactivity
  const pollers: Record<number, ReturnType<typeof setInterval>> = {}

  // --- WebSocket handler for dataset.status events ---
  const unsubWs = ws.on('dataset.status', (data: WsDatasetEvent) => {
    if (data.thread_id !== chatStore.currentThreadId) return
    wsDatasets.value.set(data.file_id, data)
    wsDatasets.value = new Map(wsDatasets.value)

    // If profiling step received with connection_id, start polling profiling status
    if (data.step === 'profiling' && data.connection_id) {
      startPolling(data.connection_id)
    }
  })

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

  // --- REST fallback for page refresh ---
  const restDatasets = ref<Map<string, { file_id: string; name: string; status: string; connection_id: number | null }>>(new Map())

  async function loadConversationDatasets() {
    if (!chatStore.currentThreadId) return
    try {
      const result = await (api.chat as any).getConversationDatasets(chatStore.currentThreadId) as {
        datasets: Array<{ file_id: string; name: string; status: string; connection_id: number | null }>
      }
      const map = new Map<string, typeof result.datasets[0]>()
      for (const ds of result.datasets) {
        map.set(ds.file_id, ds)
      }
      restDatasets.value = map
    } catch {
      // Silently fail
    }
  }

  // --- Core computed ---

  const datasets = computed<DatasetStatus[]>(() => {
    const results: DatasetStatus[] = []
    const seenFileIds = new Set<string>()

    // Source 1: WebSocket events (highest priority, real-time)
    for (const [fileId, evt] of wsDatasets.value) {
      if (evt.step === 'cancelled') continue
      seenFileIds.add(fileId)

      const ds: DatasetStatus = {
        name: '',
        size: 0,
        fileId,
        connectionId: evt.connection_id ?? null,
        step: evt.step === 'failed' ? 'failed' : evt.step as DatasetStatus['step'],
        uploadedAt: new Date().toISOString(),
        schemaBuiltAt: evt.step !== 'schema' ? new Date().toISOString() : null,
        profilingStartedAt: evt.step === 'profiling' ? new Date().toISOString() : null,
        completedAt: evt.step === 'ready' ? new Date().toISOString() : null,
        rowCount: null,
        columnCount: null,
        error: evt.error ?? null,
      }

      // Enrich from REST data if available
      const rest = restDatasets.value.get(fileId)
      if (rest) {
        ds.name = rest.name
        ds.connectionId = ds.connectionId ?? rest.connection_id
      }

      // Check profiling status if we have a connection ID and step is profiling
      if (ds.connectionId && ds.step === 'profiling') {
        const profiling = profilingStatuses.value.get(ds.connectionId)
        if (profiling?.status === 'ready') {
          ds.step = 'ready'
          ds.completedAt = profiling.completedAt
        } else if (profiling?.status === 'failed') {
          ds.step = 'failed'
          ds.error = profiling.error || 'Profiling failed'
        }
      }

      results.push(ds)
    }

    // Source 2: Message attachments + agent steps (existing logic for active sessions)
    // Only scan messages after the last context_reset to avoid leaking
    // old dataset references past a "New Topic" boundary.
    const allMessages = chatStore.messages
    let resetIdx = -1
    for (let i = allMessages.length - 1; i >= 0; i--) {
      if ((allMessages[i] as any).source === 'context_reset') {
        resetIdx = i
        break
      }
    }
    const postResetMessages = resetIdx >= 0 ? allMessages.slice(resetIdx + 1) : allMessages

    const allSteps: AgentStep[] = []
    for (const msg of postResetMessages) {
      if (msg.agent_steps?.length) {
        allSteps.push(...msg.agent_steps)
      }
    }

    const datasetToolCalls = allSteps.filter(
      s => s.tool_name === 'create_dataset_from_upload' && s.step_type === 'tool_call'
    )

    for (const msg of postResetMessages) {
      if (!msg.attachments?.length) continue

      for (const att of msg.attachments) {
        if (!CSV_MIME_TYPES.has(att.type)) continue
        if (att.file_id && seenFileIds.has(att.file_id)) continue
        if (att.file_id) seenFileIds.add(att.file_id)

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

        ds.uploadedAt = msg.created_at

        const toolCall = att.file_id
          ? datasetToolCalls.find(s => s.content?.args?.file_id === att.file_id)
          : null

        if (!toolCall) {
          if (chatStore.isStreaming) {
            ds.step = 'schema'
            ds.schemaBuiltAt = null
          } else {
            ds.step = 'ready'
            ds.completedAt = msg.created_at
          }
          results.push(ds)
          continue
        }

        if (toolCall.status === 'started') {
          ds.step = 'schema'
          ds.schemaBuiltAt = null
          results.push(ds)
          continue
        }

        const result = typeof toolCall.content?.result === 'string'
          ? (() => { try { return JSON.parse(toolCall.content.result) } catch { return toolCall.content.result } })()
          : toolCall.content?.result

        if (result && !result.success) {
          ds.step = 'failed'
          ds.schemaBuiltAt = stepTimestamp(toolCall)
          ds.error = result.message || 'Dataset creation failed'
          results.push(ds)
          continue
        }

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

        const profiling = profilingStatuses.value.get(ds.connectionId)

        if (!profiling) {
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

        ds.step = 'profiling'
        ds.profilingStartedAt = ds.schemaBuiltAt
        results.push(ds)
      }
    }

    // Source 3: REST fallback (for datasets not covered by WS or attachments)
    for (const [fileId, rest] of restDatasets.value) {
      if (seenFileIds.has(fileId)) continue

      const profiling = rest.connection_id ? profilingStatuses.value.get(rest.connection_id) : null
      let step: DatasetStatus['step'] = 'profiling'
      if (rest.status === 'ready' || profiling?.status === 'ready') step = 'ready'
      else if (rest.status === 'failed' || profiling?.status === 'failed') step = 'failed'

      results.push({
        name: rest.name,
        size: 0,
        fileId,
        connectionId: rest.connection_id,
        step,
        uploadedAt: null,
        schemaBuiltAt: null,
        profilingStartedAt: null,
        completedAt: step === 'ready' ? profiling?.completedAt ?? null : null,
        rowCount: null,
        columnCount: null,
        error: step === 'failed' ? (profiling?.error || 'Processing failed') : null,
      })
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

  // Stop all polling and reload data when conversation changes
  watch(() => chatStore.currentThreadId, () => {
    stopAllPolling()
    profilingStatuses.value = new Map()
    wsDatasets.value = new Map()
    restDatasets.value = new Map()
    // Load datasets from REST for the new conversation (page refresh scenario)
    loadConversationDatasets()
  })

  // Cleanup on unmount
  onUnmounted(() => {
    stopAllPolling()
    unsubWs()
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

  async function cancelDataset(fileId: string) {
    try {
      await (api.chat as any).cancelDataset(fileId)
      wsDatasets.value.delete(fileId)
      wsDatasets.value = new Map(wsDatasets.value)
    } catch {
      // Silently fail
    }
  }

  return {
    datasets,
    wsDatasets,
    retryProfiling,
    cancelDataset,
    loadConversationDatasets,
  }
}
