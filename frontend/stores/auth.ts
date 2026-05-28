import { defineStore } from 'pinia'

export interface User {
  id: string
  email: string
  org_id: string | null
  sso_id: string | null
  auth_provider: string
  created_at: string
  role?: 'bingo_admin' | 'admin' | 'user' | null
  is_subscriber?: boolean
  // Phase 6 of multi-user-org: per-org role used to gate the Members and
  // Org Credits settings tabs in the bingo-admin plugin.
  org_role?: 'admin' | 'member' | string | null
  org_feature_flags?: Record<string, unknown>
}

export interface MaintenanceState {
  active: boolean
  bypass_active: boolean
  message: string
}

export interface AuthConfig {
  provider: string
  sso_base_url?: string
  publishable_key?: string
  google_oauth_url?: string
  maintenance?: MaintenanceState
}

const DEFAULT_MAINTENANCE: MaintenanceState = {
  active: false,
  bypass_active: false,
  message: '',
}

// Deduplication: when multiple widgets get 401 simultaneously,
// only the first call actually refreshes; others await the same promise.
let _refreshPromise: Promise<boolean> | null = null
let _fetchUserPromise: Promise<void> | null = null

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    token: null as string | null,
    refreshToken: null as string | null,
    authConfig: null as AuthConfig | null,
    maintenance: { ...DEFAULT_MAINTENANCE } as MaintenanceState,
    loading: false,
    error: null as string | null,
    isInactive: false,
    _isFirstLogin: false,
    _authInitialized: false,
  }),

  getters: {
    isAuthenticated: (state) => !!state.token && !!state.user,
    currentUser: (state) => state.user,
    hasGoogleOAuth: (state) => !!state.authConfig?.google_oauth_url,
    isAccountInactive: (state) => state.isInactive,
    isFirstLogin: (state) => state._isFirstLogin,
    authInitialized: (state) => state._authInitialized,
  },

  actions: {
    async loadAuthConfig() {
      try {
        const data = await $fetch<AuthConfig>('/api/auth/config', {
          credentials: 'include',  // send maint_bypass cookie if present
        })
        this.authConfig = data
        this.maintenance = data.maintenance
          ? { ...data.maintenance }
          : { ...DEFAULT_MAINTENANCE }
      } catch (error) {
        console.error('Failed to load auth config:', error)
      }
    },

    // ─── SSO helpers ────────────────────────────────────────────

    _ssoHeaders(): Record<string, string> {
      const headers: Record<string, string> = {}
      if (this.authConfig?.publishable_key) {
        headers['X-API-Key'] = this.authConfig.publishable_key
      }
      return headers
    },

    _redirectBaseUrl(): string {
      return process.client ? window.location.origin : ''
    },

    _parseSSOError(error: any, fallback: string): string {
      const data = error?.data
      const detail = data?.detail
      if (Array.isArray(detail) && detail.length > 0) {
        return detail.map((e: any) =>
          (e.msg || '').replace(/^Value error,\s*/i, '')
        ).join('. ')
      }
      if (typeof detail === 'string') return detail
      return data?.message || fallback
    },

    // ─── Registration ───────────────────────────────────────────

    async register(email: string, password: string) {
      this.loading = true
      this.error = null

      try {
        await $fetch('/sso-api/auth/register', {
          method: 'POST',
          headers: this._ssoHeaders(),
          body: { email, password, redirect_base_url: this._redirectBaseUrl() },
        })
        return { success: true }
      } catch (error: any) {
        this.error = this._parseSSOError(error, 'Registration failed')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    // ─── Login ──────────────────────────────────────────────────

    async login(credentials: { email: string; password: string }) {
      this.loading = true
      this.error = null

      try {
        const data = await $fetch<{ access_token: string; refresh_token: string; is_first_login?: boolean }>(
          '/sso-api/auth/login',
          {
            method: 'POST',
            headers: this._ssoHeaders(),
            body: credentials,
          }
        )
        this.token = data.access_token
        this.refreshToken = data.refresh_token
        this._isFirstLogin = data.is_first_login ?? false
        this._persistTokens()
        await this.fetchUser()
        return { success: true }
      } catch (error: any) {
        const detail = error?.data?.detail ?? ''
        const isInactiveError =
          typeof detail === 'string' &&
          (detail.toLowerCase().includes('inactive') || detail.toLowerCase().includes('deactivated'))
        if (isInactiveError) {
          this.isInactive = true
          this.error = 'Account is inactive'
        } else {
          this.error = this._parseSSOError(error, 'Login failed')
        }
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    // ─── Google OAuth ───────────────────────────────────────────

    async loginWithGoogle() {
      if (!this.authConfig?.google_oauth_url) {
        console.error('Google OAuth not available')
        return
      }
      const successUrl = encodeURIComponent(`${window.location.origin}/auth/success`)
      const errorUrl = encodeURIComponent(`${window.location.origin}/auth/error`)
      const url = `${this.authConfig.google_oauth_url}?redirect_url=${successUrl}&error_url=${errorUrl}&api_key=${this.authConfig.publishable_key}`
      window.location.href = url
    },

    // ─── SSO OAuth callback ─────────────────────────────────────

    async handleOAuthSuccess(accessToken: string, refreshToken: string, isFirstLogin?: boolean) {
      this.token = accessToken
      this.refreshToken = refreshToken
      this._isFirstLogin = isFirstLogin ?? false
      this._persistTokens()
      await this.fetchUser()
    },

    // ─── Email verification ────────────────────────────────────

    async verifyEmail(token: string) {
      this.loading = true
      this.error = null

      try {
        const data = await $fetch<{ access_token: string; refresh_token: string; is_first_login?: boolean }>(
          '/sso-api/auth/verify-email',
          {
            method: 'POST',
            headers: this._ssoHeaders(),
            body: { token },
          }
        )
        // Drop any prior session before installing the new account's tokens, so a
        // stale token (e.g. an account still logged in this browser) can't shadow the
        // freshly-verified user.
        this._clearLocalSession()
        this.token = data.access_token
        this.refreshToken = data.refresh_token
        this._isFirstLogin = data.is_first_login ?? false
        this._persistTokens()
        await this.fetchUser()
        return { success: true }
      } catch (error: any) {
        this.error = this._parseSSOError(error, 'Email verification failed')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async resendVerification(email: string) {
      try {
        await $fetch('/sso-api/auth/resend-verification', {
          method: 'POST',
          headers: this._ssoHeaders(),
          body: { email, redirect_base_url: this._redirectBaseUrl() },
        })
        return { success: true }
      } catch (error: any) {
        return { success: false, error: error.data?.message || 'Failed to resend verification' }
      }
    },

    // ─── Token refresh ──────────────────────────────────────────

    async refreshAccessToken() {
      if (_refreshPromise) return _refreshPromise
      _refreshPromise = this._doRefreshToken()
      try {
        return await _refreshPromise
      } finally {
        _refreshPromise = null
      }
    },

    async _doRefreshToken() {
      try {
        if (!this.refreshToken) return false
        const data = await $fetch<{ access_token: string }>(
          '/sso-api/auth/token/refresh',
          {
            method: 'POST',
            headers: this._ssoHeaders(),
            body: { refresh_token: this.refreshToken },
          }
        )
        this.token = data.access_token
        this._persistTokens()
        return true
      } catch {
        await this.logout()
        return false
      }
    },

    // ─── Password reset ─────────────────────────────────────────

    async forgotPassword(email: string) {
      try {
        await $fetch('/sso-api/auth/forgot-password', {
          method: 'POST',
          headers: this._ssoHeaders(),
          body: { email, redirect_base_url: this._redirectBaseUrl() },
        })
        return { success: true }
      } catch (error: any) {
        return { success: false, error: error.data?.message || error.message || 'Failed to send reset email' }
      }
    },

    async resetPassword(token: string, newPassword: string) {
      try {
        await $fetch('/sso-api/auth/reset-password', {
          method: 'POST',
          headers: this._ssoHeaders(),
          body: { token, new_password: newPassword },
        })
        return { success: true }
      } catch (error: any) {
        return { success: false, error: error.data?.message || error.message || 'Password reset failed' }
      }
    },

    // ─── User fetch & session ───────────────────────────────────

    async fetchUser() {
      if (!this.token) return
      if (_fetchUserPromise) return _fetchUserPromise
      _fetchUserPromise = this._doFetchUser()
      try {
        return await _fetchUserPromise
      } finally {
        _fetchUserPromise = null
      }
    },

    async _doFetchUser() {
      try {
        const data = await $fetch<User>('/api/auth/me', {
          headers: {
            Authorization: `Bearer ${this.token}`,
          },
        })
        this.user = data
        this.isInactive = false
      } catch (error: any) {
        if (error?.statusCode === 403 || error?.status === 403) {
          this.isInactive = true
          this.error = 'Account is inactive'
          this.token = null
          this.refreshToken = null
          if (process.client) {
            localStorage.removeItem('auth_token')
            localStorage.removeItem('auth_refresh_token')
          }
          throw error
        } else if (error?.statusCode === 401 || error?.status === 401) {
          const refreshed = await this.refreshAccessToken()
          if (refreshed) {
            try {
              const data = await $fetch<User>('/api/auth/me', {
                headers: {
                  Authorization: `Bearer ${this.token}`,
                },
              })
              this.user = data
              return
            } catch {
              // Retry also failed — fall through to logout
            }
          }
          this.logout()
        } else {
          this.logout()
        }
      }
    },

    async loadUser() {
      if (process.client) {
        const token = localStorage.getItem('auth_token')
        const refreshToken = localStorage.getItem('auth_refresh_token')
        const isFirstLogin = localStorage.getItem('auth_is_first_login')
        if (token) {
          this.token = token
          if (refreshToken) this.refreshToken = refreshToken
          if (isFirstLogin !== null) this._isFirstLogin = isFirstLogin === 'true'
          await this.fetchUser()
        }
        this._authInitialized = true
      }
    },

    // ─── Logout ─────────────────────────────────────────────────

    async logout() {
      if (this.token && this.refreshToken) {
        try {
          await $fetch('/api/auth/logout', {
            method: 'POST',
            headers: { Authorization: `Bearer ${this.token}` },
            body: { refresh_token: this.refreshToken },
          })
        } catch {
          // Ignore logout errors
        }
      }

      this._clearLocalSession()
    },

    // Tear down all client-side session state (stores, websocket, tokens,
    // localStorage). Does NOT call the SSO logout endpoint — used both by logout()
    // (after it blacklists the refresh token) and by verifyEmail() to wipe a stale
    // session before adopting a new account.
    _clearLocalSession() {
      const chatStore = useChatStore()
      const dashboardStore = useDashboardStore()
      const { disconnect, clearHandlers } = useWebSocket()

      chatStore.reset()
      dashboardStore.$resetAll()
      disconnect()
      clearHandlers()

      this.user = null
      this.token = null
      this.refreshToken = null
      this.error = null
      this.isInactive = false
      this._isFirstLogin = false
      this._authInitialized = false

      if (process.client) {
        localStorage.removeItem('auth_token')
        localStorage.removeItem('auth_refresh_token')
        localStorage.removeItem('auth_is_first_login')
      }
    },

    // ─── Persistence ────────────────────────────────────────────

    _persistTokens() {
      if (process.client) {
        if (this.token) localStorage.setItem('auth_token', this.token)
        if (this.refreshToken) localStorage.setItem('auth_refresh_token', this.refreshToken)
        localStorage.setItem('auth_is_first_login', String(!!this._isFirstLogin))
      }
    },
  },
})
