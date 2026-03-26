import { defineStore } from 'pinia'
import type { AuthChangeEvent, Session } from '@supabase/supabase-js'

export interface User {
  id: string
  email: string
  org_id: string | null
  sso_id: string | null
  auth_provider: string
  created_at: string
}

export interface AuthConfig {
  provider: string
  // SSO fields
  sso_base_url?: string
  publishable_key?: string
  google_oauth_url?: string
  // Supabase fields
  supabase_url?: string
  supabase_anon_key?: string
}

// Deduplication: when multiple widgets get 401 simultaneously,
// only the first call actually refreshes; others await the same promise.
let _refreshPromise: Promise<boolean> | null = null

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    token: null as string | null,
    refreshToken: null as string | null,
    authConfig: null as AuthConfig | null,
    loading: false,
    error: null as string | null,
  }),

  getters: {
    isAuthenticated: (state) => !!state.token && !!state.user,
    currentUser: (state) => state.user,
    isSSO: (state) => state.authConfig?.provider === 'sso',
    isSupabase: (state) => state.authConfig?.provider === 'supabase',
  },

  actions: {
    async loadAuthConfig() {
      try {
        const data = await $fetch<AuthConfig>('/api/auth/config')
        this.authConfig = data
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
        if (this.isSupabase) {
          const supabase = useSupabase()
          const { error } = await supabase.auth.signUp({ email, password })
          if (error) {
            this.error = error.message
            return { success: false, error: error.message }
          }
          return { success: true }
        }

        // SSO
        await $fetch('/sso-api/auth/register', {
          method: 'POST',
          headers: this._ssoHeaders(),
          body: { email, password },
        })
        return { success: true }
      } catch (error: any) {
        this.error = this.isSSO
          ? this._parseSSOError(error, 'Registration failed')
          : (error.message || 'Registration failed')
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
        if (this.isSupabase) {
          const supabase = useSupabase()
          const { data, error } = await supabase.auth.signInWithPassword(credentials)
          if (error) {
            this.error = error.message
            return { success: false, error: error.message }
          }
          this.token = data.session?.access_token ?? null
          this._persistTokens()
          await this.fetchUser()
          return { success: true }
        }

        // SSO
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
        this.error = this.isSSO
          ? this._parseSSOError(error, 'Login failed')
          : (error.message || 'Login failed')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    // ─── Google OAuth ───────────────────────────────────────────

    async loginWithGoogle() {
      if (this.isSupabase) {
        try {
          const supabase = useSupabase()
          const { error } = await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: {
              redirectTo: `${window.location.origin}/auth/success`,
            },
          })
          if (error) console.error('Google OAuth error:', error.message)
        } catch (error: any) {
          console.error('Google OAuth error:', error)
        }
        return
      }

      // SSO
      if (!this.authConfig) {
        console.error('Auth config not loaded')
        return
      }
      const successUrl = encodeURIComponent(`${window.location.origin}/auth/success`)
      const errorUrl = encodeURIComponent(`${window.location.origin}/auth/error`)
      const url = `${this.authConfig.google_oauth_url}?redirect_url=${successUrl}&error_url=${errorUrl}&api_key=${this.authConfig.publishable_key}`
      window.location.href = url
    },

    // ─── SSO OAuth callback ─────────────────────────────────────

    async handleOAuthSuccess(accessToken: string, refreshToken: string) {
      this.token = accessToken
      this.refreshToken = refreshToken
      this._persistTokens()
      await this.fetchUser()
    },

    // ─── Email verification (SSO) ──────────────────────────────

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
        if (this.isSupabase) {
          const supabase = useSupabase()
          const { data, error } = await supabase.auth.refreshSession()
          if (error || !data.session) {
            await this.logout()
            return false
          }
          this.token = data.session.access_token
          this._persistTokens()
          return true
        }

        // SSO
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
        if (this.isSupabase) {
          const supabase = useSupabase()
          const { error } = await supabase.auth.resetPasswordForEmail(email, {
            redirectTo: `${window.location.origin}/auth/reset-password`,
          })
          if (error) return { success: false, error: error.message }
          return { success: true }
        }

        // SSO
        await $fetch('/sso-api/auth/forgot-password', {
          method: 'POST',
          headers: this._ssoHeaders(),
          body: { email },
        })
        return { success: true }
      } catch (error: any) {
        return { success: false, error: error.data?.message || error.message || 'Failed to send reset email' }
      }
    },

    async resetPassword(token: string, newPassword: string) {
      try {
        if (this.isSupabase) {
          const supabase = useSupabase()
          const { error } = await supabase.auth.updateUser({ password: newPassword })
          if (error) return { success: false, error: error.message }
          return { success: true }
        }

        // SSO
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

      try {
        const data = await $fetch<User>('/api/auth/me', {
          headers: {
            Authorization: `Bearer ${this.token}`,
          },
        })
        this.user = data
      } catch (error: any) {
        if (error?.statusCode === 401 || error?.status === 401) {
          // Try refreshing the token before giving up
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

    handleAuthStateChange(event: AuthChangeEvent, session: Session | null) {
      if (session) {
        this.token = session.access_token
        this._persistTokens()
      } else if (event === 'SIGNED_OUT') {
        this.token = null
        this.user = null
        if (process.client) {
          localStorage.removeItem('auth_token')
        }
      }
    },

    // ─── Logout ─────────────────────────────────────────────────

    async logout() {
      if (this.isSupabase) {
        try {
          const supabase = useSupabase()
          await supabase.auth.signOut()
        } catch {
          // Ignore signOut errors
        }
      } else if (this.token && this.refreshToken) {
        // SSO: notify backend to invalidate refresh token
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

      if (process.client) {
        localStorage.removeItem('auth_token')
        localStorage.removeItem('auth_refresh_token')
      }
    },

    // ─── Persistence ────────────────────────────────────────────

    _persistTokens() {
      if (process.client) {
        if (this.token) localStorage.setItem('auth_token', this.token)
        if (this.refreshToken) localStorage.setItem('auth_refresh_token', this.refreshToken)
      }
    },
  },
})
