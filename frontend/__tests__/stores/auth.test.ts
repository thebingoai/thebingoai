import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// ── Global mocks required by auth store ────────────────────────────────
vi.stubGlobal('$fetch', vi.fn())
// Extend the real process object instead of replacing it — Pinia reads process.env.NODE_ENV
;(globalThis as any).process = { ...process, client: true }

const storage: Record<string, string> = {}
vi.stubGlobal('localStorage', {
  getItem: vi.fn((key: string) => storage[key] ?? null),
  setItem: vi.fn((key: string, val: string) => { storage[key] = val }),
  removeItem: vi.fn((key: string) => { delete storage[key] }),
})

vi.mock('~/composables/useSupabase', () => ({
  useSupabase: vi.fn(),
}))

// Auth store's logout() calls these — mock them so the store module can load
vi.mock('~/stores/chat', () => ({
  useChatStore: () => ({ reset: vi.fn() }),
}))
vi.mock('~/stores/dashboard', () => ({
  useDashboardStore: () => ({ $resetAll: vi.fn() }),
}))
vi.mock('~/composables/useWebSocket', () => ({
  useWebSocket: () => ({ disconnect: vi.fn(), clearHandlers: vi.fn() }),
}))

import { useAuthStore } from '~/stores/auth'

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Clear storage between tests
    for (const key of Object.keys(storage)) delete storage[key]
  })

  // ── Initial state ──────────────────────────────────────────────────
  it('has correct initial state', () => {
    const store = useAuthStore()
    expect(store.user).toBeNull()
    expect(store.token).toBeNull()
    expect(store.refreshToken).toBeNull()
    expect(store.authConfig).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  // ── isAuthenticated ────────────────────────────────────────────────
  it('isAuthenticated returns false when no token', () => {
    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(false)
  })

  it('isAuthenticated returns false when token set but no user', () => {
    const store = useAuthStore()
    store.token = 'some-token'
    expect(store.isAuthenticated).toBe(false)
  })

  it('isAuthenticated returns true when both token and user exist', () => {
    const store = useAuthStore()
    store.token = 'some-token'
    store.user = {
      id: '1',
      email: 'test@example.com',
      org_id: null,
      sso_id: null,
      auth_provider: 'sso',
      created_at: '2024-01-01',
    }
    expect(store.isAuthenticated).toBe(true)
  })

  // ── isSSO / isSupabase ─────────────────────────────────────────────
  it('isSSO returns true when authConfig.provider is sso', () => {
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    expect(store.isSSO).toBe(true)
    expect(store.isSupabase).toBe(false)
  })

  it('isSupabase returns true when authConfig.provider is supabase', () => {
    const store = useAuthStore()
    store.authConfig = { provider: 'supabase' }
    expect(store.isSupabase).toBe(true)
    expect(store.isSSO).toBe(false)
  })

  // ── _ssoHeaders ───────────────────────────────────────────────────
  it('_ssoHeaders returns X-API-Key when publishable_key is set', () => {
    const store = useAuthStore()
    store.authConfig = { provider: 'sso', publishable_key: 'pk_test_123' }
    expect(store._ssoHeaders()).toEqual({ 'X-API-Key': 'pk_test_123' })
  })

  it('_ssoHeaders returns empty object when no publishable_key', () => {
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    expect(store._ssoHeaders()).toEqual({})
  })

  // ── _parseSSOError ─────────────────────────────────────────────────
  it('_parseSSOError parses array detail', () => {
    const store = useAuthStore()
    const error = {
      data: {
        detail: [
          { msg: 'Value error, Email is required' },
          { msg: 'Value error, Password too short' },
        ],
      },
    }
    expect(store._parseSSOError(error, 'fallback')).toBe(
      'Email is required. Password too short',
    )
  })

  it('_parseSSOError parses string detail', () => {
    const store = useAuthStore()
    const error = { data: { detail: 'Invalid credentials' } }
    expect(store._parseSSOError(error, 'fallback')).toBe('Invalid credentials')
  })

  it('_parseSSOError uses message field when no detail', () => {
    const store = useAuthStore()
    const error = { data: { message: 'Server error' } }
    expect(store._parseSSOError(error, 'fallback')).toBe('Server error')
  })

  it('_parseSSOError uses fallback when no data', () => {
    const store = useAuthStore()
    expect(store._parseSSOError({}, 'fallback')).toBe('fallback')
    expect(store._parseSSOError(null, 'fallback')).toBe('fallback')
  })
})
