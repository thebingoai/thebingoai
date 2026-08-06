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
const clearCreditStateMock = vi.fn()
vi.stubGlobal('clearCreditState', clearCreditStateMock)

const { trackEventMock } = vi.hoisted(() => ({ trackEventMock: vi.fn() }))
vi.mock('~/utils/analytics', () => ({ trackEvent: trackEventMock }))

import { useAuthStore } from '~/stores/auth'

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    for (const key of Object.keys(storage)) delete storage[key]
    vi.mocked($fetch).mockReset()
    clearCreditStateMock.mockReset()
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

  it('login() lazy-loads authConfig and sends X-API-Key when config was null at boot', async () => {
    // Simulates a failed/late boot fetch: authConfig starts null. login() must
    // fetch /api/auth/config first, then send the login with the X-API-Key header.
    vi.mocked($fetch)
      .mockResolvedValueOnce({ provider: 'sso', publishable_key: 'pk_boot_1' }) // loadAuthConfig
      .mockResolvedValueOnce({ access_token: 'at', refresh_token: 'rt' })       // login
      .mockResolvedValueOnce({ id: '1', email: 'a@b.com', org_id: null, sso_id: 's1', auth_provider: 'sso', created_at: '' }) // fetchUser
    const store = useAuthStore()
    expect(store.authConfig).toBeNull()
    const result = await store.login({ email: 'a@b.com', password: 'pass' })
    expect(result.success).toBe(true)
    expect(vi.mocked($fetch)).toHaveBeenCalledWith(
      '/sso-api/auth/login',
      expect.objectContaining({ headers: { 'X-API-Key': 'pk_boot_1' } }),
    )
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

  it('logout() clears credit state so the next account cannot read this one\'s balance', async () => {
    // Credit balance lives in useState, which is per-app rather than
    // per-component — nothing else in the teardown reaches it.
    vi.mocked($fetch).mockResolvedValueOnce({})
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    store.token = 'at'
    store.refreshToken = 'rt'
    await store.logout()
    expect(clearCreditStateMock).toHaveBeenCalled()
  })

  it('clears credit state even when the logout request fails', async () => {
    // The session is torn down locally regardless, so the reset must not be
    // stranded behind a network error.
    vi.mocked($fetch).mockRejectedValueOnce(new Error('offline'))
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    store.token = 'at'
    store.refreshToken = 'rt'
    await store.logout()
    expect(clearCreditStateMock).toHaveBeenCalled()
  })

  // ── deleteAccount ─────────────────────────────────────────────────
  it('deleteAccount() calls DELETE /api/auth/account and clears session', async () => {
    vi.mocked($fetch).mockResolvedValueOnce({})
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    store.token = 'at'
    store.refreshToken = 'rt'
    store.user = {
      id: '1', email: 'a@b.com', org_id: null, sso_id: null,
      auth_provider: 'sso', created_at: '',
    }
    await store.deleteAccount()
    expect(vi.mocked($fetch)).toHaveBeenCalledWith(
      '/api/auth/account',
      expect.objectContaining({
        method: 'DELETE',
        headers: { Authorization: 'Bearer at' },
        body: { refresh_token: 'rt' },
      }),
    )
    expect(store.token).toBeNull()
    expect(store.refreshToken).toBeNull()
    expect(store.user).toBeNull()
  })

  it('deleteAccount() clears session even when the DELETE request fails', async () => {
    vi.mocked($fetch).mockRejectedValueOnce(new Error('network'))
    const store = useAuthStore()
    store.authConfig = { provider: 'sso' }
    store.token = 'at'
    store.refreshToken = 'rt'
    store.user = {
      id: '1', email: 'a@b.com', org_id: null, sso_id: null,
      auth_provider: 'sso', created_at: '',
    }
    await expect(store.deleteAccount()).rejects.toThrow()
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

  it('_doRefreshToken() lazy-loads authConfig and sends X-API-Key when config was null at boot', async () => {
    // Persisted refresh token but a failed/late boot fetch left authConfig null.
    // The refresh must fetch config first, then send with the X-API-Key header —
    // otherwise SSO rejects it and the user is force-logged-out.
    vi.mocked($fetch)
      .mockResolvedValueOnce({ provider: 'sso', publishable_key: 'pk_boot_1' }) // loadAuthConfig
      .mockResolvedValueOnce({ access_token: 'new_at' })                        // refresh
    const store = useAuthStore()
    store.refreshToken = 'rt'
    expect(store.authConfig).toBeNull()
    const result = await store._doRefreshToken()
    expect(result).toBe(true)
    expect(vi.mocked($fetch)).toHaveBeenCalledWith(
      '/sso-api/auth/token/refresh',
      expect.objectContaining({ headers: { 'X-API-Key': 'pk_boot_1' } }),
    )
  })

  // ── lazy-load authConfig guard on every SSO flow ─────────────────────
  // When the boot config fetch failed (authConfig null), each SSO flow must
  // fetch /api/auth/config first and then send the request WITH X-API-Key.
  const CONFIG_RESP = { provider: 'sso', publishable_key: 'pk_boot_1', google_oauth_url: 'https://oauth.test/go' }
  const GENERIC_RESP = {
    access_token: 'at', refresh_token: 'rt', is_first_login: false,
    id: '1', email: 'a@b.com', org_id: null, sso_id: 's1', auth_provider: 'sso', created_at: '',
  }

  it.each([
    ['register',           '/sso-api/auth/register',            (s: any) => s.register('a@b.com', 'pw')],
    ['verifyEmail',        '/sso-api/auth/verify-email',        (s: any) => s.verifyEmail('tok')],
    ['resendVerification', '/sso-api/auth/resend-verification', (s: any) => s.resendVerification('a@b.com')],
    ['forgotPassword',     '/sso-api/auth/forgot-password',     (s: any) => s.forgotPassword('a@b.com')],
    ['resetPassword',      '/sso-api/auth/reset-password',      (s: any) => s.resetPassword('tok', 'newpw')],
  ])('%s() lazy-loads authConfig and sends X-API-Key when config was null at boot', async (_name, endpoint, call) => {
    vi.mocked($fetch).mockResolvedValue(GENERIC_RESP as any)      // default for all later calls
    vi.mocked($fetch).mockResolvedValueOnce(CONFIG_RESP as any)   // first call = loadAuthConfig
    const store = useAuthStore()
    expect(store.authConfig).toBeNull()
    await call(store)
    expect(vi.mocked($fetch).mock.calls[0][0]).toBe('/api/auth/config')
    expect(vi.mocked($fetch)).toHaveBeenCalledWith(
      endpoint,
      expect.objectContaining({ headers: { 'X-API-Key': 'pk_boot_1' } }),
    )
  })

  it('loginWithGoogle() lazy-loads authConfig then redirects with api_key when config was null at boot', async () => {
    vi.mocked($fetch).mockResolvedValueOnce(CONFIG_RESP as any)   // loadAuthConfig
    const store = useAuthStore()
    expect(store.authConfig).toBeNull()
    await store.loginWithGoogle()
    expect(vi.mocked($fetch).mock.calls[0][0]).toBe('/api/auth/config')
    expect(window.location.href).toContain('https://oauth.test/go')
    expect(window.location.href).toContain('api_key=pk_boot_1')
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

  // ── GA4 auth events ───────────────────────────────────────────────
  describe('GA4 events', () => {
    const fakeUser = { id: '1', email: 'a@b.com', org_id: null, sso_id: 's1', auth_provider: 'sso', created_at: '' }

    beforeEach(() => trackEventMock.mockClear())

    it('register fires sign_up with password method on success', async () => {
      vi.mocked($fetch).mockResolvedValueOnce({})
      const store = useAuthStore()
      store.authConfig = { provider: 'sso' }
      await store.register('a@b.com', 'pass123')
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('sign_up', { method: 'password' })
    })

    it('register fires nothing on failure', async () => {
      vi.mocked($fetch).mockRejectedValueOnce({ data: { detail: 'taken' } })
      const store = useAuthStore()
      store.authConfig = { provider: 'sso' }
      await store.register('a@b.com', 'pass123')
      expect(trackEventMock).not.toHaveBeenCalled()
    })

    it('login fires login with password method after the user is fetched', async () => {
      vi.mocked($fetch)
        .mockResolvedValueOnce({ access_token: 'at', refresh_token: 'rt' })
        .mockResolvedValueOnce(fakeUser)
      const store = useAuthStore()
      store.authConfig = { provider: 'sso' }
      await store.login({ email: 'a@b.com', password: 'pass' })
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('login', { method: 'password' })
    })

    it('login fires nothing on failure', async () => {
      vi.mocked($fetch).mockRejectedValueOnce({ data: { detail: 'bad creds' } })
      const store = useAuthStore()
      store.authConfig = { provider: 'sso' }
      await store.login({ email: 'a@b.com', password: 'nope' })
      expect(trackEventMock).not.toHaveBeenCalled()
    })

    it('handleOAuthSuccess fires sign_up with google method on first login', async () => {
      vi.mocked($fetch).mockResolvedValueOnce(fakeUser) // fetchUser
      const store = useAuthStore()
      store.authConfig = { provider: 'sso' }
      await store.handleOAuthSuccess('at', 'rt', true)
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('sign_up', { method: 'google' })
    })

    it('handleOAuthSuccess fires login with google method on returning login', async () => {
      vi.mocked($fetch).mockResolvedValueOnce(fakeUser)
      const store = useAuthStore()
      store.authConfig = { provider: 'sso' }
      await store.handleOAuthSuccess('at', 'rt', false)
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('login', { method: 'google' })
    })

    it('verifyEmail fires login with password method', async () => {
      vi.mocked($fetch)
        .mockResolvedValueOnce({ access_token: 'at', refresh_token: 'rt' })
        .mockResolvedValueOnce(fakeUser)
      const store = useAuthStore()
      store.authConfig = { provider: 'sso' }
      await store.verifyEmail('tok')
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('login', { method: 'password' })
    })

    it('logout fires once with an active session', async () => {
      vi.mocked($fetch).mockResolvedValueOnce({})
      const store = useAuthStore()
      store.authConfig = { provider: 'sso' }
      store.token = 'at'
      store.refreshToken = 'rt'
      await store.logout()
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('logout')
    })

    it('a second logout after the session is cleared fires nothing (expiry double-call guard)', async () => {
      vi.mocked($fetch).mockResolvedValue({})
      const store = useAuthStore()
      store.authConfig = { provider: 'sso' }
      store.token = 'at'
      store.refreshToken = 'rt'
      await store.logout()
      trackEventMock.mockClear()
      await store.logout() // token/user already null — the fetchHelper 401 path re-calls this
      expect(trackEventMock).not.toHaveBeenCalled()
    })
  })
})
