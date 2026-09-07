import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, watch, computed } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

// ── Mock the file-upload composable (imported by useChatStreaming) ──────
// require('vue') inside the factory avoids the hoist-order TDZ on `ref`.
const { mockAttachedFiles, mockUploadPendingDatasets } = vi.hoisted(() => {
  const { ref } = require('vue')
  return {
    mockAttachedFiles: ref([] as any[]),
    mockUploadPendingDatasets: vi.fn(
      async (_threadId?: string): Promise<{ failed: string[] } | void> => {}
    ),
  }
})
vi.mock('~/composables/useChatFileUpload', () => ({
  useChatFileUpload: () => ({
    attachedFiles: mockAttachedFiles,
    // Most cases stub only the side effect (the files gaining connection ids);
    // the `{ failed }` contract is filled in here so they don't each have to
    // repeat it. A case testing an upload failure resolves it explicitly.
    uploadPendingDatasets: async (threadId?: string) =>
      (await mockUploadPendingDatasets(threadId)) ?? { failed: [] },
  }),
}))

const CSV_MIME = 'text/csv'

/** An attachment as it looks in the composer, defaulting to a resolved CSV. */
function attachment(over: Record<string, any> = {}) {
  return {
    file: { name: 'data.csv', type: CSV_MIME, size: 10 },
    file_id: null,
    connection_id: null,
    preview_url: null,
    resolved_type: CSV_MIME,
    status: 'attached',
    ...over,
  }
}

// ── Stub Nuxt auto-imports as globals ──────────────────────────────────
vi.stubGlobal('localStorage', {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
})
vi.stubGlobal('ref', ref)
vi.stubGlobal('watch', watch)
vi.stubGlobal('computed', computed)
vi.stubGlobal('onScopeDispose', vi.fn())

// Capture the (request_id-gated) WebSocket handlers so tests can fire events, and
// the unsub returned for each registration so we can assert teardown/persistence.
const wsHandlers = new Map<string, Function>()
const wsUnsubs = new Map<string, ReturnType<typeof vi.fn>>()
// Stable across useWebSocket() calls so tests can assert what was dispatched.
const wsSend = vi.fn()
vi.stubGlobal('useWebSocket', () => ({
  on: vi.fn((type: string, handler: Function) => {
    wsHandlers.set(type, handler)
    const unsub = vi.fn()
    wsUnsubs.set(type, unsub)
    return unsub
  }),
  isConnected: ref(true),   // true → skip the reconnect/auth branch in sendMessage
  send: wsSend,
}))

/** Every `chat.send` frame dispatched so far. */
const chatSends = () => wsSend.mock.calls
  .map(c => c[0])
  .filter((f: any) => f?.type === 'chat.send')

vi.stubGlobal('useCreditBalance', () => ({ refresh: vi.fn() }))
vi.stubGlobal('useDatasetStatus', () => ({ datasets: ref([]) }))

// The dataset-only turn persists itself over REST — no agent runs, so nothing else
// would write it to the DB.
const datasetAckMock = vi.fn(async () => ({}))
vi.stubGlobal('useApi', () => ({ chat: { datasetAck: datasetAckMock } }))

const { trackEventMock } = vi.hoisted(() => ({ trackEventMock: vi.fn() }))
vi.mock('~/utils/analytics', () => ({ trackEvent: trackEventMock }))
vi.stubGlobal('useMentions', () => ({
  extractMentionConnectionIds: () => [],
  extractMentions: () => [],
}))

import { useChatStore } from '~/stores/chat'
import { useChatStreaming } from '~/composables/useChatStreaming'
import { MAX_QUERY_RESULT_ROWS } from '~/composables/_chatConstants'

// The turn's own id. query.result is a per-user broadcast, so the handler keeps
// only frames stamped with it; `ws.send` sits behind an await, so the id can't
// be read off the chat.send frame synchronously — pin it instead.
const REQUEST_ID = '11111111-1111-4111-8111-111111111111'

// Start a turn (registers handlers synchronously) and return a fire() that
// stamps each frame with the turn's request_id unless the frame sets its own.
function startTurn() {
  vi.spyOn(globalThis.crypto, 'randomUUID').mockReturnValue(REQUEST_ID)
  const { sendMessage } = useChatStreaming()
  sendMessage('hi')   // never awaited — its promise only resolves on chat.done/cleanup
  const handler = wsHandlers.get('query.result')
  expect(handler).toBeDefined()
  return (frame: any) => handler!({ request_id: REQUEST_ID, ...frame })
}

describe('useChatStreaming — query.result → query_files', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    wsUnsubs.clear()
    store = useChatStore()
    store.pendingConnectionIds = []
  })

  // The assistant placeholder is the last message sendMessage added.
  const lastMsg = () => store.messages.at(-1)!

  it('appends a QueryFile and transforms rows into result objects', () => {
    startTurn()({
      result_ref: 'r1',
      data: { columns: ['a', 'b'], rows: [[1, 2], [3, 4]], label: 'Q1', row_count: 2 },
    })

    expect(lastMsg().query_files).toEqual([
      { result_ref: 'r1', label: 'Q1', row_count: 2, col_count: 2 },
    ])
    expect(lastMsg().results).toEqual([{ a: 1, b: 2 }, { a: 3, b: 4 }])
  })

  it('dedups repeated frames with the same result_ref', () => {
    const fire = startTurn()
    const frame = { result_ref: 'r1', data: { columns: ['a'], rows: [[1]], label: 'Q', row_count: 1 } }
    fire(frame)
    fire(frame)
    expect(lastMsg().query_files).toHaveLength(1)
  })

  it('tracks each distinct result_ref in arrival order', () => {
    const fire = startTurn()
    fire({ result_ref: 'r1', data: { columns: ['a'], rows: [[1]], label: 'first' } })
    fire({ result_ref: 'r2', data: { columns: ['a'], rows: [[2]], label: 'second' } })

    const qf = lastMsg().query_files!
    expect(qf.map(f => f.result_ref)).toEqual(['r1', 'r2'])
    expect(qf.map(f => f.label)).toEqual(['first', 'second'])
  })

  it('renders the last query result, not the largest one', () => {
    // Prod, 2026-09-07: a 20-row exploratory scan ran before the 7-row weekday
    // aggregation that answered the question. Ranking by row count left the
    // scan on screen while the reply pointed at the aggregation — and under the
    // privacy floor the LLM never saw either result, so it could not notice.
    const fire = startTurn()
    fire({
      result_ref: 'explore',
      data: {
        columns: ['id'],
        rows: Array.from({ length: 20 }, (_, i) => [i]),
        label: 'sales',
      },
    })
    fire({
      result_ref: 'answer',
      data: {
        columns: ['day', 'avg'],
        rows: Array.from({ length: 7 }, (_, i) => [`d${i}`, i]),
        label: 'sales',
      },
    })

    expect(lastMsg().results).toHaveLength(7)
    expect(lastMsg().results![0]).toEqual({ day: 'd0', avg: 0 })
    // Every query still gets its own download chip.
    expect(lastMsg().query_files!.map(f => f.result_ref)).toEqual(['explore', 'answer'])
  })

  it('sets results but no query_files when result_ref is absent', () => {
    startTurn()({ data: { columns: ['a'], rows: [[1]] } })
    expect(lastMsg().results).toEqual([{ a: 1 }])
    expect(lastMsg().query_files).toBeUndefined()
  })

  it('falls back to "query" label and the raw row count', () => {
    startTurn()({
      result_ref: 'r1',
      data: { columns: ['a'], rows: [[1], [2], [3]] },   // no label, no row_count
    })
    expect(lastMsg().query_files![0].label).toBe('query')
    expect(lastMsg().query_files![0].row_count).toBe(3)
  })

  it('caps results at MAX_QUERY_RESULT_ROWS but reports the true row_count', () => {
    const rows = Array.from({ length: 60 }, (_, i) => [i])
    startTurn()({ result_ref: 'r1', data: { columns: ['a'], rows, row_count: 60 } })

    expect(lastMsg().results).toHaveLength(MAX_QUERY_RESULT_ROWS)
    expect(lastMsg().query_files![0].row_count).toBe(60)
  })
})

describe('useChatStreaming — persistent query.result handler', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    wsUnsubs.clear()
    store = useChatStore()
    store.pendingConnectionIds = []
  })

  const lastMsg = () => store.messages.at(-1)!
  const frame = (result_ref = 'r1') => ({
    result_ref,
    data: { columns: ['a'], rows: [[1]], label: 'Q', row_count: 1 },
  })

  it('survives cleanup() — a late query.result after chat.done still writes to the message', () => {
    const fire = startTurn()
    const qrUnsub = wsUnsubs.get('query.result')!

    // chat.done with no prior tokens drains instantly, so cleanup() runs synchronously
    // and tears down the per-turn handlers — but must NOT touch query.result.
    wsHandlers.get('chat.done')!({ thread_id: 't1' })
    expect(store.isStreaming).toBe(false)     // cleanup ran
    expect(qrUnsub).not.toHaveBeenCalled()    // query.result handler outlived it

    fire(frame())
    expect(lastMsg().results).toEqual([{ a: 1 }])
    expect(lastMsg().query_files).toEqual([
      { result_ref: 'r1', label: 'Q', row_count: 1, col_count: 1 },
    ])
  })

  it('is replaced at the next turn — the previous turn\'s handler is unsubscribed', () => {
    const { sendMessage } = useChatStreaming()
    sendMessage('hi')                         // turn 1
    const qrUnsub1 = wsUnsubs.get('query.result')!

    sendMessage('again')                      // turn 2 drops the previous handler
    expect(qrUnsub1).toHaveBeenCalledTimes(1)
  })

  it('drops a frame whose request_id belongs to a different turn', () => {
    const fire = (() => {
      const { sendMessage } = useChatStreaming()
      sendMessage('hi')
      return wsHandlers.get('query.result')!
    })()

    fire({ ...frame(), request_id: '__other_turn__' })
    expect(lastMsg().results).toBeUndefined()
    expect(lastMsg().query_files).toBeUndefined()
  })

  it('drops a frame with no request_id — a briefing, or a backend that never stamped one', () => {
    const fire = startTurn()

    fire({ ...frame(), request_id: undefined })
    expect(lastMsg().results).toBeUndefined()
    expect(lastMsg().query_files).toBeUndefined()
  })
})

describe('useChatStreaming — deferred dataset upload', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    wsUnsubs.clear()
    wsSend.mockClear()
    mockUploadPendingDatasets.mockReset()
    mockUploadPendingDatasets.mockResolvedValue(undefined)
    mockAttachedFiles.value = []
    store = useChatStore()
    store.currentThreadId = 't1'
    store.pendingConnectionIds = []
  })

  it('uploads pending datasets before dispatching chat.send', async () => {
    let release!: () => void
    const uploadDone = new Promise<void>(r => { release = r })
    mockUploadPendingDatasets.mockImplementation(() => uploadDone)
    mockAttachedFiles.value = [attachment()]

    const { sendMessage } = useChatStreaming()
    sendMessage('what is in here?')
    await Promise.resolve()

    // The upload is in flight — the question must not have gone out yet.
    expect(mockUploadPendingDatasets).toHaveBeenCalled()
    expect(chatSends()).toHaveLength(0)

    // The upload lands: markProcessing stamps the connection file_id.
    mockAttachedFiles.value = [attachment({
      status: 'processing', file_id: 'connection:42', connection_id: 42, sent: true,
    })]
    release()
    await new Promise(r => setTimeout(r, 0))

    // Still held — the send now also waits on documentation (see the phase-3 block).
    expect(chatSends()).toHaveLength(0)
    store.clearDocsPending(42)
    await new Promise(r => setTimeout(r, 0))

    const sends = chatSends()
    expect(sends).toHaveLength(1)
    expect(sends[0].file_ids).toEqual(['connection:42'])
  })

  it('carries the file_ids of every uploaded dataset', async () => {
    mockAttachedFiles.value = [attachment(), attachment({ file: { name: 'b.csv', type: CSV_MIME, size: 5 } })]
    mockUploadPendingDatasets.mockImplementation(async () => {
      mockAttachedFiles.value = [
        attachment({ status: 'processing', file_id: 'connection:1', connection_id: 1, sent: true }),
        attachment({ status: 'processing', file_id: 'connection:2', connection_id: 2, sent: true }),
      ]
    })

    const { sendMessage } = useChatStreaming()
    sendMessage('compare these')
    await new Promise(r => setTimeout(r, 0))
    store.clearDocsPending(1)
    store.clearDocsPending(2)
    await new Promise(r => setTimeout(r, 0))

    expect(chatSends()[0].file_ids).toEqual(['connection:1', 'connection:2'])
  })

  it('treats a text/plain .csv as a dataset when collecting file_ids', async () => {
    // Regression: the send path used to test the raw file.type, so a
    // drag-dropped CSV never reached the agent.
    mockUploadPendingDatasets.mockImplementation(async () => {
      mockAttachedFiles.value = [attachment({
        file: { name: 'report.csv', type: 'text/plain', size: 5 },
        resolved_type: CSV_MIME,
        status: 'processing', file_id: 'connection:7', connection_id: 7, sent: true,
      })]
    })
    mockAttachedFiles.value = [attachment({
      file: { name: 'report.csv', type: 'text/plain', size: 5 },
      resolved_type: CSV_MIME,
    })]

    const { sendMessage } = useChatStreaming()
    sendMessage('summarise')
    await new Promise(r => setTimeout(r, 0))
    store.clearDocsPending(7)
    await new Promise(r => setTimeout(r, 0))

    expect(chatSends()[0].file_ids).toEqual(['connection:7'])
  })

  it('sends immediately when nothing is attached', async () => {
    const { sendMessage } = useChatStreaming()
    sendMessage('hi')
    await new Promise(r => setTimeout(r, 0))

    expect(chatSends()).toHaveLength(1)
    expect(chatSends()[0].file_ids).toEqual([])
  })

  it('never puts a pending- placeholder on the wire', async () => {
    // The dashboard empty state parks its local placeholder in currentThreadId
    // while it navigates. Awaiting the upload hands control back long enough for
    // that to happen even with nothing attached, and the backend answers
    // "Conversation not found" for an id it never issued.
    store.currentThreadId = `pending-${123}`

    const { sendMessage } = useChatStreaming()
    sendMessage('what were sales last month?')
    await new Promise(r => setTimeout(r, 0))

    expect(chatSends()).toHaveLength(1)
    expect(chatSends()[0].thread_id).toBeNull()
  })

  it('reports a failed upload instead of asking about a file that never landed', async () => {
    mockAttachedFiles.value = [attachment()]
    mockUploadPendingDatasets.mockResolvedValue({ failed: ['data.csv'] })

    const { sendMessage } = useChatStreaming()
    sendMessage('')          // dataset-only: the processing WAS the request
    await new Promise(r => setTimeout(r, 0))

    // An empty message would come back as "Empty message" and bury the real cause.
    expect(chatSends()).toHaveLength(0)
    expect(datasetAckMock).not.toHaveBeenCalled()
    const assistant = store.messages.at(-1)!
    expect(assistant.role).toBe('assistant')
    expect(assistant.content).toContain('data.csv')
  })

  it('still asks the question when only some of the uploads failed', async () => {
    mockAttachedFiles.value = [
      attachment(),
      attachment({ file: { name: 'b.csv', type: CSV_MIME, size: 5 } }),
    ]
    mockUploadPendingDatasets.mockImplementation(async () => {
      mockAttachedFiles.value = [
        attachment({ status: 'error' }),
        attachment({
          file: { name: 'b.csv', type: CSV_MIME, size: 5 },
          status: 'processing', file_id: 'connection:2', connection_id: 2, sent: true,
        }),
      ]
      return { failed: ['data.csv'] }
    })

    const { sendMessage } = useChatStreaming()
    sendMessage('compare these')
    await new Promise(r => setTimeout(r, 0))
    store.clearDocsPending(2)
    await new Promise(r => setTimeout(r, 0))

    expect(chatSends()[0].file_ids).toEqual(['connection:2'])
    // The failed file's optimistic pill must stop claiming it is processing.
    const user = store.messages.find(m => m.role === 'user')!
    expect(user.attachments!.find(a => a.name === 'data.csv')!.status).toBe('error')
  })
})

/** Simulate an upload landing: the file gains a connection id. */
function uploadsAs(...connectionIds: number[]) {
  mockAttachedFiles.value = connectionIds.map((id, i) =>
    attachment({ file: { name: `f${i}.csv`, type: CSV_MIME, size: 5 } }))
  mockUploadPendingDatasets.mockImplementation(async () => {
    mockAttachedFiles.value = connectionIds.map((id, i) => attachment({
      file: { name: `f${i}.csv`, type: CSV_MIME, size: 5 },
      status: 'processing', file_id: `connection:${id}`, connection_id: id,
      row_count: 100 + i, sent: true,
    }))
  })
}

const tick = () => new Promise(r => setTimeout(r, 0))

describe('useChatStreaming — the answer waits for documentation', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    wsUnsubs.clear()
    wsSend.mockClear()
    mockUploadPendingDatasets.mockReset()
    mockAttachedFiles.value = []
    store = useChatStore()
    store.currentThreadId = 't1'
    store.pendingConnectionIds = []
  })

  it('holds chat.send while the connection is awaiting documentation', async () => {
    uploadsAs(42)
    const { sendMessage } = useChatStreaming()
    sendMessage('what is in here?')
    await tick()

    // markDocsPending was applied for the uploaded connection…
    expect(store.docsPendingConnections).toContain(42)
    expect(chatSends()).toHaveLength(0)

    // …and only clearing it releases the question.
    store.clearDocsPending(42)
    await tick()
    expect(chatSends()).toHaveLength(1)
    expect(chatSends()[0].message).toBe('what is in here?')
  })

  it('waits for both connections when two datasets are attached', async () => {
    uploadsAs(1, 2)
    const { sendMessage } = useChatStreaming()
    sendMessage('compare them')
    await tick()

    expect(store.docsPendingConnections).toEqual(expect.arrayContaining([1, 2]))

    store.clearDocsPending(1)
    await tick()
    expect(chatSends()).toHaveLength(0)   // still waiting on the second

    store.clearDocsPending(2)
    await tick()
    expect(chatSends()).toHaveLength(1)
  })

  it('is released by the self-heal that clears docsPendingConnections', async () => {
    vi.useFakeTimers()
    try {
      uploadsAs(42)
      const { sendMessage } = useChatStreaming()
      sendMessage('anything')
      await vi.advanceTimersByTimeAsync(1)
      expect(chatSends()).toHaveLength(0)

      // The 120 s ceiling fires — no permanent hang even if the backend went silent.
      await vi.advanceTimersByTimeAsync(120_000)
      expect(store.docsPendingConnections).not.toContain(42)
      expect(chatSends()).toHaveLength(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('sends without waiting when no dataset was uploaded this turn', async () => {
    mockUploadPendingDatasets.mockResolvedValue(undefined)
    const { sendMessage } = useChatStreaming()
    sendMessage('plain question')
    await tick()

    expect(store.docsPendingConnections).toEqual([])
    expect(chatSends()).toHaveLength(1)
  })

  it('empty text plus a dataset posts a follow-up instead of an agent turn', async () => {
    uploadsAs(42)
    const { sendMessage } = useChatStreaming()
    sendMessage('')
    await tick()

    // Documentation arrives with a column count.
    store.setDatasetDocs({
      connection_id: 42, table_name: 'csv_42', filename: 'f0.csv',
      table_description: null, columns: [], total_columns: 7,
    })
    store.clearDocsPending(42)
    await tick()

    expect(chatSends()).toHaveLength(0)
    const reply = store.messages.at(-1)!
    expect(reply.role).toBe('assistant')
    expect(reply.content).toContain('f0.csv')
    expect(reply.content).toContain('100 rows')
    expect(reply.content).toContain('7 columns')
    expect(store.isStreaming).toBe(false)
  })

  it('empty text with no dataset still goes to the agent', async () => {
    mockUploadPendingDatasets.mockResolvedValue(undefined)
    const { sendMessage } = useChatStreaming()
    sendMessage('')
    await tick()

    expect(chatSends()).toHaveLength(1)
  })

  it('does not wait again on a connection whose documentation already arrived', async () => {
    // Either the docs task beat the upload's HTTP response, or the upload published
    // a terminal `dataset.docs` inline because it never enqueued the task (auto-docs
    // off, inline profiling failed, an append) — that one is emitted before the
    // response, so it always wins. The ws handler has recorded and cleared it by the
    // time the send path resumes, so re-marking it pending would wait on an event
    // that has come and gone.
    uploadsAs(42)
    const landed = mockUploadPendingDatasets.getMockImplementation()!
    mockUploadPendingDatasets.mockImplementation(async () => {
      await landed()
      store.setDatasetDocs({
        connection_id: 42, table_name: 'csv_42', filename: 'f0.csv',
        table_description: null, columns: [], total_columns: 3,
      })
    })

    const { sendMessage } = useChatStreaming()
    sendMessage('what is in here?')
    await tick()

    // No clearDocsPending, no 120 s self-heal — the question goes out immediately.
    expect(store.docsPendingConnections).not.toContain(42)
    expect(chatSends()).toHaveLength(1)
  })

  it('still answers locally when an early-docs append arrives with no question', async () => {
    // The dataset-only branch keys on this turn's uploads, not on what it waited
    // for — otherwise an append whose docs landed early would fall through to the
    // agent with an empty prompt, which the backend rejects outright.
    uploadsAs(42)
    const landed = mockUploadPendingDatasets.getMockImplementation()!
    mockUploadPendingDatasets.mockImplementation(async () => {
      await landed()
      store.setDatasetDocs({
        connection_id: 42, table_name: 'csv_42', filename: 'f0.csv',
        table_description: null, columns: [], total_columns: 3,
      })
    })

    const { sendMessage } = useChatStreaming()
    sendMessage('')
    await tick()

    expect(chatSends()).toHaveLength(0)
    expect(store.messages.at(-1)!.content).toContain('f0.csv')
  })

  it('leaves a dataset retained from an earlier turn out of file_ids', async () => {
    // clearFiles() keeps sent datasets in the composer so the panel still shows
    // them. Re-sending their file_ids re-injects the whole profile into every later
    // prompt and re-persists the attachment — and they already reach the agent via
    // connection_ids and the server's thread-dataset sweep.
    const retained = attachment({
      file: { name: 'old.csv', type: CSV_MIME, size: 5 },
      status: 'ready', file_id: 'connection:9', connection_id: 9, sent: true,
    })
    mockAttachedFiles.value = [retained, attachment({ file: { name: 'f0.csv', type: CSV_MIME, size: 5 } })]
    mockUploadPendingDatasets.mockImplementation(async () => {
      mockAttachedFiles.value = [retained, attachment({
        file: { name: 'f0.csv', type: CSV_MIME, size: 5 },
        status: 'processing', file_id: 'connection:42', connection_id: 42, sent: true,
      })]
    })

    const { sendMessage } = useChatStreaming()
    sendMessage('and this one?')
    await tick()
    store.clearDocsPending(42)
    await tick()

    expect(chatSends()[0].file_ids).toEqual(['connection:42'])
  })
})

describe('useChatStreaming — the dataset-only turn is persisted', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    wsUnsubs.clear()
    wsSend.mockClear()
    datasetAckMock.mockReset().mockResolvedValue({})
    mockUploadPendingDatasets.mockReset()
    mockAttachedFiles.value = []
    store = useChatStore()
    store.currentThreadId = 't1'
    store.pendingConnectionIds = []
  })

  /** Drive a dataset-only turn to completion. */
  async function datasetOnlyTurn() {
    uploadsAs(42)
    const { sendMessage } = useChatStreaming()
    sendMessage('')
    await tick()
    store.clearDocsPending(42)
    await tick()
  }

  it('writes the turn the agent never ran', async () => {
    await datasetOnlyTurn()

    expect(datasetAckMock).toHaveBeenCalledTimes(1)
    const [threadId, fileIds, content] = datasetAckMock.mock.calls[0] as any[]
    expect(threadId).toBe('t1')
    expect(fileIds).toEqual(['connection:42'])
    expect(content).toContain('f0.csv')
    expect(content).toBe(store.messages.at(-1)!.content)
  })

  it('keeps the reply on screen when the write fails', async () => {
    datasetAckMock.mockRejectedValue(new Error('offline'))
    await datasetOnlyTurn()

    expect(store.messages.at(-1)!.content).toContain('f0.csv')
    expect(store.isStreaming).toBe(false)
  })

  it('does not write anything for an ordinary turn', async () => {
    uploadsAs(42)
    const { sendMessage } = useChatStreaming()
    sendMessage('what is in here?')
    await tick()
    store.clearDocsPending(42)
    await tick()

    expect(chatSends()).toHaveLength(1)
    expect(datasetAckMock).not.toHaveBeenCalled()
  })
})

describe('useChatStreaming — the optimistic message learns its connection ids', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    wsUnsubs.clear()
    wsSend.mockClear()
    mockUploadPendingDatasets.mockReset()
    mockAttachedFiles.value = []
    store = useChatStore()
    store.currentThreadId = 't1'
    store.pendingConnectionIds = []
  })

  const userMsg = () => store.messages.find(m => m.role === 'user')!
  const fileIds = () => userMsg().attachments!.map(a => a.file_id)

  it('rewrites the placeholders once the deferred upload returns', async () => {
    uploadsAs(101, 102)
    const { sendMessage } = useChatStreaming()
    sendMessage('analyse both of the docs')

    // Built before the upload, so all it can carry is the file's name.
    expect(fileIds()).toEqual(['__pending__:f0.csv', '__pending__:f1.csv'])

    await tick()

    // Cards, pills and the dataset-status source all key on this prefix.
    expect(fileIds()).toEqual(['connection:101', 'connection:102'])
  })

  it('leaves a file whose upload failed on its placeholder', async () => {
    const named = (name: string, over: Record<string, any> = {}) =>
      attachment({ file: { name, type: CSV_MIME, size: 5 }, ...over })

    mockAttachedFiles.value = [named('ok.csv'), named('bad.csv')]
    mockUploadPendingDatasets.mockImplementation(async () => {
      mockAttachedFiles.value = [
        named('ok.csv', {
          status: 'processing', file_id: 'connection:5', connection_id: 5, sent: true,
        }),
        named('bad.csv', { status: 'failed', error: 'Upload failed' }),
      ]
    })

    const { sendMessage } = useChatStreaming()
    sendMessage('two files')
    await tick()

    expect(fileIds()).toEqual(['connection:5', '__pending__:bad.csv'])
  })
})

describe('useChatStreaming — GA4 chat events', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    wsUnsubs.clear()
    trackEventMock.mockClear()
    store = useChatStore()
    store.pendingConnectionIds = []
  })

  it('sendMessage fires chat_message_sent with the current thread id', () => {
    store.currentThreadId = 't9'
    const { sendMessage } = useChatStreaming()
    sendMessage('hi')
    expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('chat_message_sent', {
      thread_id: 't9',
    })
  })

  it('chat.done fires chat_response_received with has_sql false when no SQL ran', () => {
    const { sendMessage } = useChatStreaming()
    sendMessage('hi')
    trackEventMock.mockClear()
    // No streamed tokens → the drip is drained → finalize runs synchronously.
    wsHandlers.get('chat.done')!({ thread_id: 't1' })
    expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('chat_response_received', {
      thread_id: 't1',
      has_sql: false,
    })
  })

  it('chat.done fires has_sql true when an execute_query tool call ran', () => {
    const { sendMessage } = useChatStreaming()
    sendMessage('sum revenue')
    trackEventMock.mockClear()
    wsHandlers.get('chat.tool_call')!({ content: { tool: 'execute_query', args: {} } })
    wsHandlers.get('chat.done')!({ thread_id: 't1' })
    expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('chat_response_received', {
      thread_id: 't1',
      has_sql: true,
    })
  })

  it('chat.done fires has_sql true when execute_query is nested in data_agent sub_steps', () => {
    const { sendMessage } = useChatStreaming()
    sendMessage('sum revenue')
    trackEventMock.mockClear()
    wsHandlers.get('chat.tool_call')!({
      content: { tool: 'data_agent', args: {} },
    })
    // The tool_result handler copies result.steps into the step's sub_steps.
    wsHandlers.get('chat.tool_result')!({
      content: { tool: 'data_agent', result: { steps: [{ tool_name: 'execute_query' }] } },
    })
    wsHandlers.get('chat.done')!({ thread_id: 't1' })
    expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('chat_response_received', {
      thread_id: 't1',
      has_sql: true,
    })
  })
})
