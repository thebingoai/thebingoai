import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { reactive, computed } from 'vue'

// ── Stub Vue reactivity as globals (Nuxt auto-imports) ─────────────

vi.stubGlobal('reactive', reactive)
vi.stubGlobal('computed', computed)

// ── Mock WebSocket ─────────────────────────────────────────────────

class MockWebSocket {
  static instances: MockWebSocket[] = []
  static OPEN = 1
  static CONNECTING = 0
  static CLOSING = 2
  static CLOSED = 3
  url: string
  onopen: ((ev: Event) => void) | null = null
  onclose: ((ev: any) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null
  readyState = 1
  send = vi.fn()
  close = vi.fn()
  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }
}

vi.stubGlobal('WebSocket', MockWebSocket)

// ── Mock useAuthStore (Nuxt auto-import) ───────────────────────────

vi.stubGlobal('useAuthStore', () => ({
  token: 'test-jwt-token',
  isAuthenticated: true,
  refreshAccessToken: vi.fn().mockResolvedValue(true),
}))

// Need to reset module-level singleton state between tests
let useWebSocket: typeof import('~/composables/useWebSocket').useWebSocket

describe('useWebSocket', () => {
  beforeEach(async () => {
    MockWebSocket.instances = []
    vi.resetModules()

    // Re-stub after resetModules (resetModules clears module cache but globals persist)
    vi.stubGlobal('reactive', reactive)
    vi.stubGlobal('computed', computed)
    vi.stubGlobal('WebSocket', MockWebSocket)
    vi.stubGlobal('useAuthStore', () => ({
      token: 'test-jwt-token',
      isAuthenticated: true,
      refreshAccessToken: vi.fn().mockResolvedValue(true),
    }))

    const mod = await import('~/composables/useWebSocket')
    useWebSocket = mod.useWebSocket
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('connect creates WebSocket with correct URL containing token', () => {
    const ws = useWebSocket()
    ws.connect('my-token')

    expect(MockWebSocket.instances).toHaveLength(1)
    const created = MockWebSocket.instances[0]
    expect(created.url).toContain('/ws?token=my-token')
    expect(created.url).toMatch(/^wss?:\/\//)
  })

  it('disconnect closes WebSocket and resets state', () => {
    const ws = useWebSocket()
    ws.connect('tok')

    const created = MockWebSocket.instances[0]
    created.onopen?.(new Event('open'))

    expect(ws.isConnected.value).toBe(true)

    ws.disconnect()
    expect(created.close).toHaveBeenCalledWith(1000, 'User logout')
    expect(ws.isConnected.value).toBe(false)
    expect(ws.connectionState.value).toBe('disconnected')
  })

  it('on() registers handler and receives messages by type', () => {
    const ws = useWebSocket()
    const handler = vi.fn()

    ws.on('chat_message', handler)
    ws.connect('tok')

    const created = MockWebSocket.instances[0]
    created.onopen?.(new Event('open'))
    created.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({ type: 'chat_message', text: 'hello' }),
    }))

    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'chat_message', text: 'hello' })
    )
  })

  it('send() sends JSON through WebSocket when connected', () => {
    const ws = useWebSocket()
    ws.connect('tok')

    const created = MockWebSocket.instances[0]
    created.readyState = 1 // WebSocket.OPEN
    created.onopen?.(new Event('open'))

    ws.send({ type: 'ping', data: 42 })
    expect(created.send).toHaveBeenCalledWith(JSON.stringify({ type: 'ping', data: 42 }))
  })

  it('clearHandlers() removes all registered handlers', () => {
    const ws = useWebSocket()
    const handler1 = vi.fn()
    const handler2 = vi.fn()

    ws.on('type_a', handler1)
    ws.on('type_b', handler2)
    ws.clearHandlers()

    ws.connect('tok')
    const created = MockWebSocket.instances[0]
    created.onopen?.(new Event('open'))
    created.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({ type: 'type_a' }),
    }))
    created.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({ type: 'type_b' }),
    }))

    expect(handler1).not.toHaveBeenCalled()
    expect(handler2).not.toHaveBeenCalled()
  })

  it('on() returns unsubscribe function that removes specific handler', () => {
    const ws = useWebSocket()
    const handler = vi.fn()

    const unsub = ws.on('event', handler)
    unsub()

    ws.connect('tok')
    const created = MockWebSocket.instances[0]
    created.onopen?.(new Event('open'))
    created.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({ type: 'event' }),
    }))

    expect(handler).not.toHaveBeenCalled()
  })
})
