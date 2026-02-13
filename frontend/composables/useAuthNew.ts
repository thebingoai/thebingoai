import { ref, computed } from 'vue'
import type { User, LoginRequest, RegisterRequest, TokenResponse } from '~/types/auth'

const user = ref<User | null>(null)
const token = ref<string | null>(null)
const loading = ref(false)

export const useAuthNew = () => {
  const router = useRouter()
  const config = useRuntimeConfig()
  const baseURL = config.public.apiBaseUrl || 'http://localhost:8000'

  // Load auth state from localStorage on mount
  if (process.client) {
    const storedToken = localStorage.getItem('auth_token')
    if (storedToken) {
      token.value = storedToken
      loadUser()
    }
  }

  const isAuthenticated = computed(() => !!token.value)

  async function apiRequest<T>(url: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {})
    }

    if (token.value) {
      headers['Authorization'] = `Bearer ${token.value}`
    }

    const response = await fetch(`${baseURL}${url}`, {
      ...options,
      headers
    })

    if (!response.ok) {
      if (response.status === 401) {
        logout()
      }
      const error = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(error.detail || 'Request failed')
    }

    return response.json()
  }

  async function login(credentials: LoginRequest) {
    loading.value = true
    try {
      const response = await apiRequest<TokenResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify(credentials)
      })

      token.value = response.access_token

      if (process.client) {
        localStorage.setItem('auth_token', response.access_token)
      }

      await loadUser()
      router.push('/')
    } finally {
      loading.value = false
    }
  }

  async function register(data: RegisterRequest) {
    loading.value = true
    try {
      await apiRequest('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify(data)
      })
      await login({ email: data.email, password: data.password })
    } finally {
      loading.value = false
    }
  }

  async function loadUser() {
    try {
      user.value = await apiRequest<User>('/api/auth/me')
    } catch (error) {
      logout()
    }
  }

  function logout() {
    token.value = null
    user.value = null

    if (process.client) {
      localStorage.removeItem('auth_token')
    }

    router.push('/login')
  }

  return {
    user: computed(() => user.value),
    token: computed(() => token.value),
    loading: computed(() => loading.value),
    isAuthenticated,
    login,
    register,
    logout,
    loadUser,
    apiRequest
  }
}
