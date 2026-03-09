import { defineStore } from 'pinia'

export interface User {
  id: string
  email: string
  org_id: string | null
  created_at: string
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface RegisterCredentials {
  email: string
  password: string
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    token: null as string | null,
    loading: false,
    error: null as string | null
  }),

  getters: {
    isAuthenticated: (state) => !!state.token && !!state.user,
    currentUser: (state) => state.user
  },

  actions: {
    async login(credentials: LoginCredentials) {
      this.loading = true
      this.error = null

      try {
        const response = await $fetch('/api/auth/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: credentials
        })

        const data = response as { access_token: string; token_type: string }
        this.token = data.access_token

        // Persist token
        if (process.client) {
          localStorage.setItem('auth_token', this.token)
        }

        // Fetch user info
        await this.fetchUser()

        return { success: true }
      } catch (error: any) {
        this.error = error.data?.detail || 'Login failed'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async register(credentials: RegisterCredentials) {
      this.loading = true
      this.error = null

      try {
        const response = await $fetch('/api/auth/register', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: credentials
        })

        const data = response as { access_token: string; token_type: string }
        this.token = data.access_token

        // Persist token
        if (process.client) {
          localStorage.setItem('auth_token', this.token)
        }

        // Fetch user info
        await this.fetchUser()

        return { success: true }
      } catch (error: any) {
        this.error = error.data?.detail || 'Registration failed'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async fetchUser() {
      if (!this.token) return

      try {
        const data = await $fetch('/api/auth/me', {
          headers: {
            Authorization: `Bearer ${this.token}`
          }
        })
        this.user = data as User
      } catch (error: any) {
        // Only logout on 401 (invalid token), not on network errors
        if (error?.statusCode === 401 || error?.status === 401) {
          this.logout()
        }
      }
    },

    async loadUser() {
      // Load token from localStorage
      if (process.client) {
        const token = localStorage.getItem('auth_token')
        if (token) {
          this.token = token
          await this.fetchUser()
        }
      }
    },

    logout() {
      const chatStore = useChatStore()
      const dashboardStore = useDashboardStore()
      const { disconnect, clearHandlers } = useWebSocket()

      chatStore.reset()
      dashboardStore.$resetAll()
      disconnect()
      clearHandlers()

      this.user = null
      this.token = null
      this.error = null

      if (process.client) {
        localStorage.removeItem('auth_token')
      }
    }
  }
})
