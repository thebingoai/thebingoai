import { defineStore } from 'pinia'

export interface User {
  id: string
  email: string
  org_id: string | null
  sso_id: string | null
  auth_provider: string
  created_at: string
}

export interface SSOConfig {
  sso_base_url: string
  publishable_key: string
  google_oauth_url: string
}

// Deduplication: when multiple widgets get 401 simultaneously,
// only the first call actually refreshes; others await the same promise.
let _refreshPromise: Promise<boolean> | null = null

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    token: null as string | null,
    refreshToken: null as string | null,
    ssoConfig: null as SSOConfig | null,
    verificationPending: false,
    pendingEmail: null as string | null,
    loading: false,
    error: null as string | null,
  }),

  getters: {
    isAuthenticated: (state) => !!state.token && !!state.user,
    currentUser: (state) => state.user,
  },

  actions: {
    async loadSSOConfig() {
      try {
        const data = await $fetch<SSOConfig>('/api/auth/config')
        this.ssoConfig = data
      } catch (error) {
        console.error('Failed to load SSO config:', error)
      }
    },

    _parseSSOError(error: any, fallback: string): string {
      const data = error?.data
      // FastAPI/Pydantic 422: { detail: [{ type, loc, msg, ... }] }
      const detail = data?.detail
      if (Array.isArray(detail) && detail.length > 0) {
        return detail.map((e: any) =>
          (e.msg || '').replace(/^Value error,\s*/i, '')
        ).join('. ')
      }
      // String detail (e.g. "Invalid email or password")
      if (typeof detail === 'string') return detail
      // Top-level message field
      return data?.message || fallback
    },

    _ssoHeaders(): Record<string, string> {
      const headers: Record<string, string> = {}
      if (this.ssoConfig?.publishable_key) {
        headers['X-API-Key'] = this.ssoConfig.publishable_key
      }
      return headers
    },

    async register(email: string, password: string) {
      this.loading = true
      this.error = null

      try {
        await $fetch('/sso-api/auth/register', {
          method: 'POST',
          headers: this._ssoHeaders(),
          body: { email, password },
        })

        this.verificationPending = true
        this.pendingEmail = email
        return { success: true }
      } catch (error: any) {
        this.error = this._parseSSOError(error, 'Registration failed')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async verifyEmail(token: string) {
      this.loading = true
      this.error = null

      try {
        const data = await $fetch<{ access_token: string; refresh_token: string }>(
          '/sso-api/auth/verify-email',
          {
            method: 'POST',
            headers: this._ssoHeaders(),
            body: { token },
          }
        )

        this.token = data.access_token
        this.refreshToken = data.refresh_token
        this.verificationPending = false
        this.pendingEmail = null
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
          body: { email },
        })
        return { success: true }
      } catch (error: any) {
        return { success: false, error: error.data?.message || 'Failed to resend verification' }
      }
    },

    async login(credentials: { email: string; password: string }) {
      this.loading = true
      this.error = null

      try {
        const data = await $fetch<{ access_token: string; refresh_token: string }>(
          '/sso-api/auth/login',
          {
            method: 'POST',
            headers: this._ssoHeaders(),
            body: credentials,
          }
        )

        this.token = data.access_token
        this.refreshToken = data.refresh_token
        this._persistTokens()
        await this.fetchUser()
        return { success: true }
      } catch (error: any) {
        this.error = this._parseSSOError(error, 'Login failed')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    loginWithGoogle() {
      if (!this.ssoConfig) {
        console.error('SSO config not loaded')
        return
      }
      const successUrl = encodeURIComponent(`${window.location.origin}/auth/success`)
      const errorUrl = encodeURIComponent(`${window.location.origin}/auth/error`)
      const url = `${this.ssoConfig.google_oauth_url}?redirect_url=${successUrl}&error_url=${errorUrl}&api_key=${this.ssoConfig.publishable_key}`
      window.location.href = url
    },

    async handleOAuthSuccess(accessToken: string, refreshToken: string) {
      this.token = accessToken
      this.refreshToken = refreshToken
      this._persistTokens()
      await this.fetchUser()
    },

    async refreshAccessToken() {
      if (!this.refreshToken) return false
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
        const data = await $fetch<{ access_token: string }>(
          '/sso-api/auth/token/refresh',
          {
            method: 'POST',
            headers: this._ssoHeaders(),
            body: { refresh_token: this.refreshToken },
          }
        )

        this.token = data.access_token
        if (process.client) {
          localStorage.setItem('auth_token', this.token)
        }
        return true
      } catch {
        await this.logout()
        return false
      }
    },

    async forgotPassword(email: string) {
      try {
        await $fetch('/sso-api/auth/forgot-password', {
          method: 'POST',
          headers: this._ssoHeaders(),
          body: { email },
        })
        return { success: true }
      } catch (error: any) {
        return { success: false, error: error.data?.message || 'Failed to send reset email' }
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
        return { success: false, error: error.data?.message || 'Password reset failed' }
      }
    },

    async fetchUser() {
      if (!this.token) return

      try {
        const data = await $fetch<User>('/api/auth/me', {
          headers: {
            Authorization: `Bearer ${this.token}`,
          },
        })
        this.user = data
      } catch (error: any) {
        if (error?.statusCode === 401 || error?.status === 401) {
          this.logout()
        }
      }
    },

    async loadUser() {
      if (process.client) {
        const token = localStorage.getItem('auth_token')
        const refreshToken = localStorage.getItem('auth_refresh_token')
        if (token) {
          this.token = token
          if (refreshToken) this.refreshToken = refreshToken
          await this.fetchUser()
        }
      }
    },

    async logout() {
      // Notify backend to invalidate SSO refresh token
      if (this.token && this.refreshToken) {
        try {
          await $fetch('/api/auth/logout', {
            method: 'POST',
            headers: { Authorization: `Bearer ${this.token}` },
            body: { refresh_token: this.refreshToken },
          })
        } catch {
          // Ignore logout errors - clear local state regardless
        }
      }

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
      // ssoConfig is static app config — keep it across logout so login still works
      this.error = null
      this.verificationPending = false
      this.pendingEmail = null

      if (process.client) {
        localStorage.removeItem('auth_token')
        localStorage.removeItem('auth_refresh_token')
      }
    },

    _persistTokens() {
      if (process.client) {
        if (this.token) localStorage.setItem('auth_token', this.token)
        if (this.refreshToken) localStorage.setItem('auth_refresh_token', this.refreshToken)
      }
    },
  },
})
