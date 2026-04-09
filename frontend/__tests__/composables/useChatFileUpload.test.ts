import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { ref, computed } from 'vue'

// ── Stub Nuxt auto-imports as globals (before module import) ──────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', vi.fn())
vi.stubGlobal('onUnmounted', vi.fn())
vi.stubGlobal('useRuntimeConfig', () => ({ public: { chatFileMaxSizeMb: 50 } }))
// Add missing URL methods for happy-dom
if (!URL.createObjectURL) {
  (URL as any).createObjectURL = vi.fn(() => 'blob:mock')
}
if (!URL.revokeObjectURL) {
  (URL as any).revokeObjectURL = vi.fn()
}

const mockChatStore = {
  currentThreadId: null as string | null,
  setCurrentThread: vi.fn(),
  addConversation: vi.fn(),
}
vi.stubGlobal('useChatStore', () => mockChatStore)

const mockUploadChatFiles = vi.fn()
const mockCreateConversation = vi.fn()
const mockUploadDataset = vi.fn()
vi.stubGlobal('useApi', () => ({
  chat: {
    uploadChatFiles: mockUploadChatFiles,
    createConversation: mockCreateConversation,
  },
  connections: {
    uploadDataset: mockUploadDataset,
  },
}))

// Use dynamic import to ensure stubs are applied before module loads
let useChatFileUpload: any

beforeAll(async () => {
  const mod = await import('~/composables/useChatFileUpload')
  useChatFileUpload = mod.useChatFileUpload
})

describe('useChatFileUpload', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockChatStore.currentThreadId = null
    const { clearFiles } = useChatFileUpload()
    clearFiles()
  })

  it('routes CSV files through connectionsApi.uploadDataset', async () => {
    mockCreateConversation.mockResolvedValue({ thread_id: 'new-thread' })
    mockUploadDataset.mockResolvedValue({ id: 42, name: 'test', row_count: 10 })

    const { addFiles, attachedFiles } = useChatFileUpload()
    const file = new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })
    await addFiles([file])

    // Should NOT call uploadChatFiles for CSV
    expect(mockUploadChatFiles).not.toHaveBeenCalled()
    // Should call uploadDataset with thread_id
    expect(mockUploadDataset).toHaveBeenCalledWith(
      file,
      undefined,
      expect.any(Function),
      'new-thread'
    )
    // Should create conversation first
    expect(mockCreateConversation).toHaveBeenCalled()
    expect(mockChatStore.setCurrentThread).toHaveBeenCalledWith('new-thread')
    // File should be ready with connection_id
    expect(attachedFiles.value[0].status).toBe('ready')
    expect(attachedFiles.value[0].connection_id).toBe(42)
  })

  it('routes non-dataset files through chatApi.uploadChatFiles', async () => {
    mockChatStore.currentThreadId = 'existing-thread'
    mockUploadChatFiles.mockResolvedValue({
      files: [{ file_id: 'f1', thread_id: 'existing-thread' }],
      thread_id: 'existing-thread',
    })

    const { addFiles } = useChatFileUpload()
    const file = new File([new ArrayBuffer(100)], 'photo.png', { type: 'image/png' })
    await addFiles([file])

    // Should call uploadChatFiles for images
    expect(mockUploadChatFiles).toHaveBeenCalled()
    // Should NOT call uploadDataset
    expect(mockUploadDataset).not.toHaveBeenCalled()
  })

  it('uses existing thread_id for dataset uploads', async () => {
    mockChatStore.currentThreadId = 'existing-thread'
    mockUploadDataset.mockResolvedValue({ id: 42, name: 'test', row_count: 10 })

    const { addFiles } = useChatFileUpload()
    const file = new File(['a,b\n1,2'], 'data.csv', { type: 'text/csv' })
    await addFiles([file])

    // Should NOT create a new conversation
    expect(mockCreateConversation).not.toHaveBeenCalled()
    // Should pass existing thread_id
    expect(mockUploadDataset).toHaveBeenCalledWith(
      file,
      undefined,
      expect.any(Function),
      'existing-thread'
    )
  })
})
