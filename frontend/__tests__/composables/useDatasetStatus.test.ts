import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, computed, watch } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

// ── Stub Nuxt auto-imports as globals ──────────────────────────────

vi.stubGlobal('localStorage', {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
})
vi.stubGlobal('$fetch', vi.fn())
;(globalThis as any).process = { ...process, client: true }

// Vue reactivity globals (Nuxt auto-imports these)
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)
vi.stubGlobal('onUnmounted', vi.fn())

// useApi global (Nuxt auto-imports composables)
const mockGetProfilingStatus = vi.fn()
const mockReprofile = vi.fn()
vi.stubGlobal('useApi', () => ({
  connections: {
    getProfilingStatus: mockGetProfilingStatus,
    reprofile: mockReprofile,
  },
}))

vi.mock('~/stores/dashboard', () => ({
  useDashboardStore: () => ({ $resetAll: vi.fn() }),
}))
vi.mock('~/composables/useWebSocket', () => ({
  useWebSocket: () => ({ disconnect: vi.fn(), clearHandlers: vi.fn() }),
}))

import { useChatStore } from '~/stores/chat'
import type { Message, FileAttachment, AgentStep } from '~/stores/chat'
import { useDatasetStatus } from '~/composables/useDatasetStatus'

// ── Helpers ────────────────────────────────────────────────────────

function csvAttachment(overrides: Partial<FileAttachment> = {}): FileAttachment {
  return {
    name: 'data.csv',
    size: 1024,
    type: 'text/csv',
    file_id: 'file-1',
    preview_url: null,
    status: 'ready',
    ...overrides,
  }
}

function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: `msg-${Math.random()}`,
    role: 'user',
    content: '',
    created_at: '2024-01-01T00:00:00Z',
    ...overrides,
  }
}

function toolCallStep(overrides: Partial<AgentStep> = {}): AgentStep {
  return {
    agent_type: 'orchestrator',
    step_type: 'tool_call',
    tool_name: 'create_dataset_from_upload',
    content: {},
    status: 'completed',
    created_at: '2024-01-01T00:01:00Z',
    ...overrides,
  }
}

describe('useDatasetStatus', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGetProfilingStatus.mockReset()
    mockReprofile.mockReset()
  })

  it('returns empty datasets when there are no messages', () => {
    const { datasets } = useDatasetStatus()
    expect(datasets.value).toEqual([])
  })

  it('returns uploading status for attachment with status "uploading"', () => {
    const store = useChatStore()
    store.messages = [
      makeMessage({
        attachments: [csvAttachment({ status: 'uploading', file_id: null })],
      }),
    ]

    const { datasets } = useDatasetStatus()
    expect(datasets.value).toHaveLength(1)
    expect(datasets.value[0].step).toBe('uploading')
    expect(datasets.value[0].name).toBe('data.csv')
  })

  it('returns failed status for attachment with status "error"', () => {
    const store = useChatStore()
    store.messages = [
      makeMessage({
        attachments: [csvAttachment({ status: 'error' })],
      }),
    ]

    const { datasets } = useDatasetStatus()
    expect(datasets.value).toHaveLength(1)
    expect(datasets.value[0].step).toBe('failed')
    expect(datasets.value[0].error).toBe('Upload failed')
  })

  it('returns schema step when tool call is in "started" status', () => {
    const store = useChatStore()
    store.messages = [
      makeMessage({
        attachments: [csvAttachment({ file_id: 'file-1' })],
        agent_steps: [
          toolCallStep({
            status: 'started',
            content: { args: { file_id: 'file-1' } },
          }),
        ],
      }),
    ]

    const { datasets } = useDatasetStatus()
    expect(datasets.value).toHaveLength(1)
    expect(datasets.value[0].step).toBe('schema')
  })

  it('returns failed step when tool call result has success=false', () => {
    const store = useChatStore()
    store.messages = [
      makeMessage({
        attachments: [csvAttachment({ file_id: 'file-2' })],
        agent_steps: [
          toolCallStep({
            content: {
              args: { file_id: 'file-2' },
              result: JSON.stringify({ success: false, message: 'Bad CSV' }),
            },
          }),
        ],
      }),
    ]

    const { datasets } = useDatasetStatus()
    expect(datasets.value).toHaveLength(1)
    expect(datasets.value[0].step).toBe('failed')
    expect(datasets.value[0].error).toBe('Bad CSV')
  })

  it('returns profiling step when schema built and connection_id present', () => {
    const store = useChatStore()
    store.messages = [
      makeMessage({
        attachments: [csvAttachment({ file_id: 'file-3' })],
        agent_steps: [
          toolCallStep({
            content: {
              args: { file_id: 'file-3' },
              result: JSON.stringify({
                success: true,
                connection_id: 42,
                row_count: 100,
                columns: ['a', 'b'],
              }),
            },
          }),
        ],
      }),
    ]

    const { datasets } = useDatasetStatus()
    expect(datasets.value).toHaveLength(1)
    expect(datasets.value[0].step).toBe('profiling')
    expect(datasets.value[0].connectionId).toBe(42)
    expect(datasets.value[0].rowCount).toBe(100)
    expect(datasets.value[0].columnCount).toBe(2)
  })

  it('ignores non-CSV/Excel attachments', () => {
    const store = useChatStore()
    store.messages = [
      makeMessage({
        attachments: [
          csvAttachment({ type: 'image/png', name: 'screenshot.png' }),
        ],
      }),
    ]

    const { datasets } = useDatasetStatus()
    expect(datasets.value).toHaveLength(0)
  })
})
