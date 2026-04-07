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

// Stub window.location.origin for redirect_base_url
vi.stubGlobal('window', { location: { origin: 'http://localhost:3000' } })

// Auth store's logout() uses auto-imported composables — stub them globally
vi.stubGlobal('useChatStore', () => ({ reset: vi.fn() }))
vi.stubGlobal('useDashboardStore', () => ({ $resetAll: vi.fn() }))
vi.stubGlobal('useWebSocket', () => ({ disconnect: vi.fn(), clearHandlers: vi.fn() }))

import { useAuthStore } from '~/stores/auth'

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    for (const key of Object.keys(storage)) delete storage[key]
    vi.mocked($fetch).mockReset()
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

  // ── hasGoogleOAuth ────────────────────────────────────────────────
  it('hasGoogleOAuth returns false when google_oauth_url is absent', () => {
    const store = useAuthStore()
    store.authConfig = { provider: 'sso', sso_base_url: 'https://sso.example.com' }
    expect(store.hasGoogleOAuth).toBe(false)
  })

  it('hasGoogleOAuth returns true when google_oauth_url is present', () => {
    const store = useAuthStore()
    store.authConfig = {
      provider: 'sso',
      sso_base_url: 'https://sso.example.com',
      google_oauth_url: 'https://sso.example.com/api/v1/oauth/google',
    }
    expect(store.hasGoogleOAuth).toBe(true)
  })

  // ── register ──────────────────────────────────────────────────────
  it('register() calls /sso-api/auth/register', async () => {
    vi.mocked($fetch).mockResolvedValueOnce({})
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    const result = await store.register('a@b.com', 'pass123')
    expect(result.success).toBe(true)
    expect(vi.mocked($fetch)).toHaveBeenCalledWith(
      '/sso-api/auth/register',
      expect.objectContaining({ method: 'POST', body: { email: 'a@b.com', password: 'pass123', redirect_base_url: 'http://localhost:3000' } }),
    )
  })

  // ── login ─────────────────────────────────────────────────────────
  it('login() calls /sso-api/auth/login', async () => {
    vi.mocked($fetch)
      .mockResolvedValueOnce({ access_token: 'at', refresh_token: 'rt' })
      .mockResolvedValueOnce({ id: '1', email: 'a@b.com', org_id: null, sso_id: 's1', auth_provider: 'sso', created_at: '' })
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    const result = await store.login({ email: 'a@b.com', password: 'pass' })
    expect(result.success).toBe(true)
    expect(store.token).toBe('at')
    expect(store.refreshToken).toBe('rt')
  })

  // ── logout ────────────────────────────────────────────────────────
  it('logout() calls /api/auth/logout with refresh token', async () => {
    vi.mocked($fetch).mockResolvedValueOnce({})
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    store.token = 'at'
    store.refreshToken = 'rt'
    await store.logout()
    expect(vi.mocked($fetch)).toHaveBeenCalledWith(
      '/api/auth/logout',
      expect.objectContaining({
        method: 'POST',
        body: { refresh_token: 'rt' },
      }),
    )
    expect(store.token).toBeNull()
    expect(store.user).toBeNull()
  })

  // ── _doRefreshToken ───────────────────────────────────────────────
  it('_doRefreshToken() calls /sso-api/auth/token/refresh', async () => {
    vi.mocked($fetch).mockResolvedValueOnce({ access_token: 'new_at' })
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    store.refreshToken = 'rt'
    store.token = 'old'
    const result = await store._doRefreshToken()
    expect(result).toBe(true)
    expect(store.token).toBe('new_at')
  })

  // ── forgotPassword ────────────────────────────────────────────────
  it('forgotPassword() calls /sso-api/auth/forgot-password', async () => {
    vi.mocked($fetch).mockResolvedValueOnce({})
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    const result = await store.forgotPassword('a@b.com')
    expect(result.success).toBe(true)
    expect(vi.mocked($fetch)).toHaveBeenCalledWith(
      '/sso-api/auth/forgot-password',
      expect.objectContaining({ method: 'POST', body: { email: 'a@b.com', redirect_base_url: 'http://localhost:3000' } }),
    )
  })

  // ── resendVerification ────────────────────────────────────────────
  it('resendVerification() calls /sso-api/auth/resend-verification with redirect_base_url', async () => {
    vi.mocked($fetch).mockResolvedValueOnce({})
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    const result = await store.resendVerification('a@b.com')
    expect(result.success).toBe(true)
    expect(vi.mocked($fetch)).toHaveBeenCalledWith(
      '/sso-api/auth/resend-verification',
      expect.objectContaining({ method: 'POST', body: { email: 'a@b.com', redirect_base_url: 'http://localhost:3000' } }),
    )
  })

  // ── resetPassword ─────────────────────────────────────────────────
  it('resetPassword() calls /sso-api/auth/reset-password', async () => {
    vi.mocked($fetch).mockResolvedValueOnce({})
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    const result = await store.resetPassword('tok', 'newpass')
    expect(result.success).toBe(true)
    expect(vi.mocked($fetch)).toHaveBeenCalledWith(
      '/sso-api/auth/reset-password',
      expect.objectContaining({ method: 'POST', body: { token: 'tok', new_password: 'newpass' } }),
    )
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

  // ── No Supabase imports ───────────────────────────────────────────
  it('store has no isSSO or isSupabase getters', () => {
    const store = useAuthStore()
    expect('isSSO' in store).toBe(false)
    expect('isSupabase' in store).toBe(false)
  })
})
