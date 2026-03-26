/**
 * WebSocket composable — persistent bidirectional connection to /ws.
 *
 * Features:
 * - JWT auth via ?token= query param
 * - Auto-reconnect with exponential backoff (1s → 30s cap)
 * - 30s ping/pong keepalive
 * - Typed event handler registry
 */

type WsHandler = (data: any) => void
type Unsubscribe = () => void

interface WsState {
  ws: WebSocket | null
  isConnected: boolean
  connectionState: 'disconnected' | 'connecting' | 'connected' | 'error'
}

const state = reactive<WsState>({
  ws: null,
  isConnected: false,
  connectionState: 'disconnected',
})

const handlers = new Map<string, Set<WsHandler>>()
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let keepaliveTimer: ReturnType<typeof setInterval> | null = null
let reconnectDelay = 1000
const MAX_RECONNECT_DELAY = 30_000
let _connectFn: ((token?: string) => void) | null = null

function _emit(type: string, data: any) {
  handlers.get(type)?.forEach(fn => fn(data))
  // Also emit to wildcard handlers
  handlers.get('*')?.forEach(fn => fn({ type, ...data }))
}

function _startKeepalive() {
  _stopKeepalive()
  keepaliveTimer = setInterval(() => {
    if (state.ws?.readyState === WebSocket.OPEN) {
      state.ws.send(JSON.stringify({ type: 'ping' }))
    }
  }, 30_000)
}

function _stopKeepalive() {
  if (keepaliveTimer !== null) {
    clearInterval(keepaliveTimer)
    keepaliveTimer = null
  }
}

function _scheduleReconnect(token: string) {
  if (reconnectTimer !== null) return
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    _connectFn?.(token)
  }, reconnectDelay)
  reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY)
}

export function useWebSocket() {
  const authStore = useAuthStore()

  function connect(token?: string) {
    const t = token || authStore.token
    if (!t) return

    // Close existing connection cleanly
    if (state.ws) {
      state.ws.onclose = null
      state.ws.close()
      state.ws = null
    }

    state.connectionState = 'connecting'

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    // In dev the backend is on :8000; in prod the WS endpoint is on same host
    const host = import.meta.dev
      ? `${window.location.hostname}:8000`
      : window.location.host
    const url = `${protocol}//${host}/ws?token=${encodeURIComponent(t)}`

    const ws = new WebSocket(url)
    state.ws = ws

    ws.onopen = () => {
      state.isConnected = true
      state.connectionState = 'connected'
      reconnectDelay = 1000 // reset backoff on successful connect
      _startKeepalive()
      _emit('connected', {})
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const type = data.type
        if (type) _emit(type, data)
      } catch (e) {
        console.error('[WS] Failed to parse message:', event.data, e)
      }
    }

    ws.onclose = (event) => {
      state.isConnected = false
      state.connectionState = event.wasClean ? 'disconnected' : 'error'
      state.ws = null
      _stopKeepalive()
      _emit('disconnected', { code: event.code, reason: event.reason })

      // Auth failure — try refreshing token before giving up
      if (event.code === 4003) {
        authStore.refreshAccessToken().then(ok => {
          if (ok) _scheduleReconnect(authStore.token!)
        })
        return
      }

      // No token at all — cannot reconnect
      if (event.code === 4001) return

      // Normal disconnect — reconnect if still authenticated
      if (authStore.isAuthenticated) {
        _scheduleReconnect(t)
      }
    }

    ws.onerror = () => {
      state.connectionState = 'error'
    }
  }

  _connectFn = connect

  function disconnect() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    _stopKeepalive()
    if (state.ws) {
      state.ws.onclose = null
      state.ws.close(1000, 'User logout')
      state.ws = null
    }
    state.isConnected = false
    state.connectionState = 'disconnected'
  }

  function send(data: object) {
    if (state.ws?.readyState === WebSocket.OPEN) {
      state.ws.send(JSON.stringify(data))
    } else {
      console.warn('[WS] Cannot send — not connected')
    }
  }

  function on(type: string, handler: WsHandler): Unsubscribe {
    if (!handlers.has(type)) handlers.set(type, new Set())
    handlers.get(type)!.add(handler)
    return () => handlers.get(type)?.delete(handler)
  }

  function clearHandlers() {
    handlers.clear()
  }

  return {
    connect,
    disconnect,
    send,
    on,
    clearHandlers,
    isConnected: computed(() => state.isConnected),
    connectionState: computed(() => state.connectionState),
  }
}
