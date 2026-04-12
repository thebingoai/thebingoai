import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// ── Global mocks ────────────────────────────────────────────────────
const storage: Record<string, string> = {}
vi.stubGlobal('localStorage', {
  getItem: vi.fn((key: string) => storage[key] ?? null),
  setItem: vi.fn((key: string, val: string) => { storage[key] = val }),
  removeItem: vi.fn((key: string) => { delete storage[key] }),
})

import { useChatStore } from '~/stores/chat'
import type { Conversation, Message } from '~/stores/chat'

// ── Helpers ─────────────────────────────────────────────────────────
function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: `msg-${Date.now()}-${Math.random()}`,
    role: 'user',
    content: 'hello',
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

function makeConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: `thread-${Date.now()}-${Math.random()}`,
    title: 'Test Chat',
    type: 'task',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    message_count: 0,
    ...overrides,
  }
}

describe('chat store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    for (const key of Object.keys(storage)) delete storage[key]
  })

  // ── Initial state ──────────────────────────────────────────────────
  it('has correct initial state', () => {
    const store = useChatStore()
    expect(store.conversations).toEqual([])
    expect(store.currentThreadId).toBeNull()
    expect(store.messages).toEqual([])
    expect(store.inputText).toBe('')
    expect(store.isStreaming).toBe(false)
    expect(store.conversationsLoaded).toBe(false)
  })

  // ── addMessage ────────────────────────────────────────────────────
  it('addMessage pushes to messages array', () => {
    const store = useChatStore()
    const msg = makeMessage({ content: 'first' })
    store.addMessage(msg)
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].content).toBe('first')

    store.addMessage(makeMessage({ content: 'second' }))
    expect(store.messages).toHaveLength(2)
  })

  // ── updateLastMessage ─────────────────────────────────────────────
  it('updateLastMessage merges updates into last message', () => {
    const store = useChatStore()
    store.addMessage(makeMessage({ content: 'original' }))
    store.updateLastMessage({ content: 'updated', sql: 'SELECT 1' })
    expect(store.messages[0].content).toBe('updated')
    expect(store.messages[0].sql).toBe('SELECT 1')
  })

  it('updateLastMessage does nothing when messages are empty', () => {
    const store = useChatStore()
    // Should not throw
    store.updateLastMessage({ content: 'noop' })
    expect(store.messages).toHaveLength(0)
  })

  // ── setConversations ──────────────────────────────────────────────
  it('setConversations sets conversations and marks loaded', () => {
    const store = useChatStore()
    const convs = [makeConversation({ id: 'c1' }), makeConversation({ id: 'c2' })]
    store.setConversations(convs)
    expect(store.conversations).toHaveLength(2)
    expect(store.conversationsLoaded).toBe(true)
  })

  // ── currentConversation ───────────────────────────────────────────
  it('currentConversation returns matching thread', () => {
    const store = useChatStore()
    const conv = makeConversation({ id: 'thread-42', title: 'My Chat' })
    store.setConversations([conv])
    store.currentThreadId = 'thread-42'
    expect(store.currentConversation?.title).toBe('My Chat')
  })

  it('currentConversation returns undefined when no match', () => {
    const store = useChatStore()
    store.setConversations([makeConversation({ id: 'thread-1' })])
    store.currentThreadId = 'nonexistent'
    expect(store.currentConversation).toBeUndefined()
  })

  // ── permanentConversation ─────────────────────────────────────────
  it('permanentConversation returns first permanent type', () => {
    const store = useChatStore()
    store.setConversations([
      makeConversation({ id: 'task-1', type: 'task' }),
      makeConversation({ id: 'perm-1', type: 'permanent', title: 'General' }),
      makeConversation({ id: 'perm-2', type: 'permanent', title: 'Second' }),
    ])
    expect(store.permanentConversation?.id).toBe('perm-1')
  })

  it('permanentConversation returns null when none exist', () => {
    const store = useChatStore()
    store.setConversations([makeConversation({ type: 'task' })])
    expect(store.permanentConversation).toBeNull()
  })

  // ── taskConversations ─────────────────────────────────────────────
  it('taskConversations filters and sorts by updated_at desc', () => {
    const store = useChatStore()
    store.setConversations([
      makeConversation({ id: 'older', type: 'task', updated_at: '2024-01-01T00:00:00Z' }),
      makeConversation({ id: 'perm', type: 'permanent', updated_at: '2024-06-01T00:00:00Z' }),
      makeConversation({ id: 'newer', type: 'task', updated_at: '2024-03-01T00:00:00Z' }),
    ])
    const tasks = store.taskConversations
    expect(tasks).toHaveLength(2)
    expect(tasks[0].id).toBe('newer')
    expect(tasks[1].id).toBe('older')
  })

  // ── startNewChat ──────────────────────────────────────────────────
  it('startNewChat resets chat state', () => {
    const store = useChatStore()
    store.currentThreadId = 'thread-1'
    store.messages = [makeMessage()]
    store.inputText = 'some text'
    store.isStreaming = true
    store.expandedThinking.add('msg-1')

    store.startNewChat()

    expect(store.currentThreadId).toBeNull()
    expect(store.messages).toEqual([])
    expect(store.inputText).toBe('')
    expect(store.isStreaming).toBe(false)
    expect(store.expandedThinking.size).toBe(0)
  })

  // ── moveToArchived ────────────────────────────────────────────────
  it('moveToArchived moves conversation from active to archived', () => {
    const store = useChatStore()
    const conv = makeConversation({ id: 'thread-1', title: 'To Archive' })
    store.setConversations([conv, makeConversation({ id: 'thread-2' })])

    store.moveToArchived('thread-1')

    expect(store.conversations).toHaveLength(1)
    expect(store.conversations[0].id).toBe('thread-2')
    expect(store.archivedConversations).toHaveLength(1)
    expect(store.archivedConversations[0].id).toBe('thread-1')
  })

  // ── moveFromArchived ──────────────────────────────────────────────
  it('moveFromArchived moves conversation from archived to active', () => {
    const store = useChatStore()
    const conv = makeConversation({ id: 'thread-1', title: 'Restore Me' })
    store.setConversations([])
    store.setArchivedConversations([conv])

    store.moveFromArchived('thread-1')

    expect(store.archivedConversations).toHaveLength(0)
    expect(store.conversations).toHaveLength(1)
    expect(store.conversations[0].title).toBe('Restore Me')
  })

  // ── toggleThinking ────────────────────────────────────────────────
  it('toggleThinking toggles message in expandedThinking set', () => {
    const store = useChatStore()
    expect(store.expandedThinking.has('msg-1')).toBe(false)

    store.toggleThinking('msg-1')
    expect(store.expandedThinking.has('msg-1')).toBe(true)

    store.toggleThinking('msg-1')
    expect(store.expandedThinking.has('msg-1')).toBe(false)
  })

  // ── incrementUnread / clearUnread ─────────────────────────────────
  it('incrementUnread only increments when thread is not current', () => {
    const store = useChatStore()
    const conv = makeConversation({ id: 'thread-1', unread_count: 0 })
    store.setConversations([conv])
    store.currentThreadId = 'thread-other'

    store.incrementUnread('thread-1')
    expect(store.conversations[0].unread_count).toBe(1)

    store.incrementUnread('thread-1')
    expect(store.conversations[0].unread_count).toBe(2)
  })

  it('incrementUnread does not increment when thread is current', () => {
    const store = useChatStore()
    const conv = makeConversation({ id: 'thread-1', unread_count: 0 })
    store.setConversations([conv])
    store.currentThreadId = 'thread-1'

    store.incrementUnread('thread-1')
    expect(store.conversations[0].unread_count).toBe(0)
  })

  it('clearUnread resets unread count to zero', () => {
    const store = useChatStore()
    const conv = makeConversation({ id: 'thread-1', unread_count: 5 })
    store.setConversations([conv])

    store.clearUnread('thread-1')
    expect(store.conversations[0].unread_count).toBe(0)
  })

  // ── appendConversations ───────────────────────────────────────────
  it('appendConversations adds new conversations', () => {
    const store = useChatStore()
    store.setConversations([makeConversation({ id: 'c1' })])

    store.appendConversations([makeConversation({ id: 'c2' }), makeConversation({ id: 'c3' })])

    expect(store.conversations).toHaveLength(3)
    expect(store.conversations.map(c => c.id)).toContain('c2')
    expect(store.conversations.map(c => c.id)).toContain('c3')
  })

  it('appendConversations deduplicates by id', () => {
    const store = useChatStore()
    store.setConversations([makeConversation({ id: 'c1' }), makeConversation({ id: 'c2' })])

    // c2 already exists, c3 is new
    store.appendConversations([makeConversation({ id: 'c2' }), makeConversation({ id: 'c3' })])

    expect(store.conversations).toHaveLength(3)
    expect(store.conversations.filter(c => c.id === 'c2')).toHaveLength(1)
  })

  // ── resetConversationPagination ───────────────────────────────────
  it('resetConversationPagination resets all pagination state', () => {
    const store = useChatStore()
    store.conversationHasMore = true
    store.conversationOffset = 50
    store.isLoadingMoreConversations = true

    store.resetConversationPagination()

    expect(store.conversationHasMore).toBe(false)
    expect(store.conversationOffset).toBe(0)
    expect(store.isLoadingMoreConversations).toBe(false)
  })

  // ── reset clears pagination ───────────────────────────────────────
  it('reset clears pagination state', () => {
    const store = useChatStore()
    store.conversationHasMore = true
    store.conversationOffset = 199
    store.isLoadingMoreConversations = true

    store.reset()

    expect(store.conversationHasMore).toBe(false)
    expect(store.conversationOffset).toBe(0)
    expect(store.isLoadingMoreConversations).toBe(false)
  })

  // ── moveToArchived decrements offset ──────────────────────────────
  it('moveToArchived decrements conversationOffset', () => {
    const store = useChatStore()
    const conv = makeConversation({ id: 'thread-1' })
    store.setConversations([conv])
    store.conversationOffset = 10

    store.moveToArchived('thread-1')

    expect(store.conversationOffset).toBe(9)
  })

  it('moveToArchived does not decrement offset below 0', () => {
    const store = useChatStore()
    const conv = makeConversation({ id: 'thread-1' })
    store.setConversations([conv])
    store.conversationOffset = 0

    store.moveToArchived('thread-1')

    expect(store.conversationOffset).toBe(0)
  })
})
