# Phase 09: Frontend Authentication & Connections

## Objective

Build Nuxt 4 frontend for authentication (login/register), database connections management, with JWT storage, auth middleware, and API layer.

## Prerequisites

- Phase 02: Authentication API
- Phase 03: Database Connectors API

## Files to Create

### Layouts & Pages
- `frontend/layouts/default.vue` - Main layout with navigation
- `frontend/pages/login.vue` - Login page
- `frontend/pages/register.vue` - Registration page
- `frontend/pages/connections/index.vue` - Connections list
- `frontend/pages/connections/[id].vue` - Edit connection
- `frontend/pages/connections/new.vue` - Create connection

### Composables
- `frontend/composables/useAuth.ts` - Auth state and methods
- `frontend/composables/useApi.ts` - API client with auth headers
- `frontend/composables/useConnections.ts` - Connections CRUD

### Middleware
- `frontend/middleware/auth.ts` - Auth guard middleware

### Types
- `frontend/types/auth.ts` - Auth types
- `frontend/types/connection.ts` - Connection types
- `frontend/types/api.ts` - API response types

### Components
- `frontend/components/ConnectionCard.vue` - Connection display card
- `frontend/components/ConnectionForm.vue` - Connection form
- `frontend/components/ConnectionTestButton.vue` - Test connection button
- `frontend/components/Navbar.vue` - Navigation bar

## Implementation Details

### 1. Auth Composable (frontend/composables/useAuth.ts)

```typescript
import { ref, computed } from 'vue'
import type { User, LoginRequest, RegisterRequest, TokenResponse } from '~/types/auth'

const user = ref<User | null>(null)
const token = ref<string | null>(null)
const loading = ref(false)

export const useAuth = () => {
  const router = useRouter()
  const api = useApi()

  // Load auth state from localStorage on mount
  if (process.client) {
    const storedToken = localStorage.getItem('auth_token')
    if (storedToken) {
      token.value = storedToken
      loadUser()
    }
  }

  const isAuthenticated = computed(() => !!token.value)

  async function login(credentials: LoginRequest) {
    loading.value = true
    try {
      const response = await api.post<TokenResponse>('/api/auth/login', credentials)
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
      await api.post('/api/auth/register', data)
      await login({ email: data.email, password: data.password })
    } finally {
      loading.value = false
    }
  }

  async function loadUser() {
    try {
      user.value = await api.get<User>('/api/auth/me')
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
    user,
    token,
    loading,
    isAuthenticated,
    login,
    register,
    logout,
    loadUser
  }
}
```

### 2. API Composable (frontend/composables/useApi.ts)

```typescript
import type { FetchOptions } from 'ofetch'

export const useApi = () => {
  const config = useRuntimeConfig()
  const auth = useAuth()

  const baseURL = config.public.apiBaseUrl || 'http://localhost:8000'

  async function request<T>(url: string, options: FetchOptions = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {})
    }

    // Add auth token if available
    if (auth.token.value) {
      headers['Authorization'] = `Bearer ${auth.token.value}`
    }

    try {
      return await $fetch<T>(url, {
        ...options,
        baseURL,
        headers
      })
    } catch (error: any) {
      if (error.status === 401) {
        // Token expired or invalid
        auth.logout()
      }
      throw error
    }
  }

  return {
    get: <T>(url: string, options?: FetchOptions) =>
      request<T>(url, { ...options, method: 'GET' }),

    post: <T>(url: string, body?: any, options?: FetchOptions) =>
      request<T>(url, { ...options, method: 'POST', body }),

    put: <T>(url: string, body?: any, options?: FetchOptions) =>
      request<T>(url, { ...options, method: 'PUT', body }),

    delete: <T>(url: string, options?: FetchOptions) =>
      request<T>(url, { ...options, method: 'DELETE' })
  }
}
```

### 3. Auth Middleware (frontend/middleware/auth.ts)

```typescript
export default defineNuxtRouteMiddleware((to, from) => {
  const auth = useAuth()

  // Public routes that don't require auth
  const publicRoutes = ['/login', '/register']

  if (!auth.isAuthenticated.value && !publicRoutes.includes(to.path)) {
    return navigateTo('/login')
  }

  if (auth.isAuthenticated.value && publicRoutes.includes(to.path)) {
    return navigateTo('/')
  }
})
```

### 4. Login Page (frontend/pages/login.vue)

```vue
<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4">
    <div class="max-w-md w-full space-y-8">
      <div>
        <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">
          Sign in to your account
        </h2>
      </div>

      <form class="mt-8 space-y-6" @submit.prevent="handleLogin">
        <div class="rounded-md shadow-sm -space-y-px">
          <div>
            <label for="email" class="sr-only">Email address</label>
            <input
              id="email"
              v-model="email"
              type="email"
              required
              class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
              placeholder="Email address"
            />
          </div>
          <div>
            <label for="password" class="sr-only">Password</label>
            <input
              id="password"
              v-model="password"
              type="password"
              required
              class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
              placeholder="Password"
            />
          </div>
        </div>

        <div v-if="error" class="text-red-600 text-sm">
          {{ error }}
        </div>

        <div>
          <button
            type="submit"
            :disabled="loading"
            class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
          >
            {{ loading ? 'Signing in...' : 'Sign in' }}
          </button>
        </div>

        <div class="text-center">
          <NuxtLink to="/register" class="text-indigo-600 hover:text-indigo-500">
            Don't have an account? Register
          </NuxtLink>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  layout: false,
  middleware: []
})

const auth = useAuth()

const email = ref('')
const password = ref('')
const error = ref('')
const loading = computed(() => auth.loading.value)

async function handleLogin() {
  error.value = ''
  try {
    await auth.login({ email: email.value, password: password.value })
  } catch (e: any) {
    error.value = e.data?.detail || 'Login failed'
  }
}
</script>
```

### 5. Connections List Page (frontend/pages/connections/index.vue)

```vue
<template>
  <div class="container mx-auto px-4 py-8">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold">Database Connections</h1>
      <NuxtLink
        to="/connections/new"
        class="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700"
      >
        Add Connection
      </NuxtLink>
    </div>

    <div v-if="loading" class="text-center py-12">
      <p class="text-gray-500">Loading connections...</p>
    </div>

    <div v-else-if="connections.length === 0" class="text-center py-12">
      <p class="text-gray-500 mb-4">No database connections yet</p>
      <NuxtLink
        to="/connections/new"
        class="text-indigo-600 hover:text-indigo-500"
      >
        Add your first connection
      </NuxtLink>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <ConnectionCard
        v-for="conn in connections"
        :key="conn.id"
        :connection="conn"
        @delete="handleDelete"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: 'auth'
})

const { connections, loading, fetchConnections, deleteConnection } = useConnections()

onMounted(() => {
  fetchConnections()
})

async function handleDelete(id: number) {
  if (confirm('Are you sure you want to delete this connection?')) {
    await deleteConnection(id)
    await fetchConnections()
  }
}
</script>
```

### 6. Connection Form Component (frontend/components/ConnectionForm.vue)

```vue
<template>
  <form @submit.prevent="handleSubmit" class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-700">Connection Name</label>
      <input
        v-model="form.name"
        type="text"
        required
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
      />
    </div>

    <div>
      <label class="block text-sm font-medium text-gray-700">Database Type</label>
      <select
        v-model="form.db_type"
        required
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
      >
        <option value="postgres">PostgreSQL</option>
        <option value="mysql">MySQL</option>
      </select>
    </div>

    <div class="grid grid-cols-2 gap-4">
      <div>
        <label class="block text-sm font-medium text-gray-700">Host</label>
        <input
          v-model="form.host"
          type="text"
          required
          class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700">Port</label>
        <input
          v-model.number="form.port"
          type="number"
          required
          class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
        />
      </div>
    </div>

    <div>
      <label class="block text-sm font-medium text-gray-700">Database</label>
      <input
        v-model="form.database"
        type="text"
        required
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
      />
    </div>

    <div>
      <label class="block text-sm font-medium text-gray-700">Username</label>
      <input
        v-model="form.username"
        type="text"
        required
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
      />
    </div>

    <div>
      <label class="block text-sm font-medium text-gray-700">Password</label>
      <input
        v-model="form.password"
        type="password"
        required
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
      />
    </div>

    <div v-if="error" class="text-red-600 text-sm">
      {{ error }}
    </div>

    <div class="flex space-x-4">
      <button
        type="submit"
        :disabled="loading"
        class="flex-1 bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 disabled:opacity-50"
      >
        {{ loading ? 'Saving...' : 'Save Connection' }}
      </button>

      <ConnectionTestButton :connection="form" />
    </div>
  </form>
</template>

<script setup lang="ts">
import type { ConnectionCreate } from '~/types/connection'

const props = defineProps<{
  initialData?: Partial<ConnectionCreate>
}>()

const emit = defineEmits<{
  submit: [data: ConnectionCreate]
}>()

const form = reactive<ConnectionCreate>({
  name: props.initialData?.name || '',
  db_type: props.initialData?.db_type || 'postgres',
  host: props.initialData?.host || 'localhost',
  port: props.initialData?.port || 5432,
  database: props.initialData?.database || '',
  username: props.initialData?.username || '',
  password: props.initialData?.password || ''
})

const loading = ref(false)
const error = ref('')

async function handleSubmit() {
  error.value = ''
  loading.value = true
  try {
    emit('submit', form)
  } catch (e: any) {
    error.value = e.data?.detail || 'Failed to save connection'
  } finally {
    loading.value = false
  }
}
</script>
```

## Testing & Verification

### Manual Testing Steps

1. **Start frontend dev server**:
   ```bash
   cd frontend
   npm run dev
   ```

2. **Test registration**:
   - Navigate to http://localhost:3000/register
   - Fill form and submit
   - Should redirect to home after successful registration

3. **Test login**:
   - Navigate to http://localhost:3000/login
   - Enter credentials
   - Should redirect to home and show navbar with user email

4. **Test auth middleware**:
   - Logout
   - Try to access http://localhost:3000/connections
   - Should redirect to /login

5. **Test connection CRUD**:
   - Login
   - Click "Add Connection"
   - Fill form with valid database credentials
   - Test connection (button should show success/failure)
   - Save connection
   - Should redirect to connections list
   - Edit connection
   - Delete connection

## MCP Browser Testing

Use chrome-devtools MCP:

```typescript
// Navigate to login page
await navigate_page({ url: 'http://localhost:3000/login', type: 'url' })
await take_snapshot()

// Fill login form
await fill({ uid: 'email-input', value: 'test@example.com' })
await fill({ uid: 'password-input', value: 'password123' })
await click({ uid: 'login-button' })

// Wait for redirect and verify navbar
await wait_for({ text: 'Database Connections' })
await take_snapshot()

// Test connection creation
await click({ uid: 'add-connection-button' })
await take_snapshot()
```

## Code Review Checklist

- [ ] JWT stored in localStorage (with expiry check)
- [ ] Auth middleware protects routes
- [ ] API client automatically adds auth headers
- [ ] 401 responses trigger logout
- [ ] Forms have validation and error display
- [ ] Loading states prevent double-submission
- [ ] Passwords are masked (type="password")
- [ ] Test connection before saving
- [ ] Responsive design (mobile-friendly)
- [ ] Tailwind CSS used consistently

## Done Criteria

1. User can register and login
2. JWT persists across page refreshes
3. Auth middleware redirects unauthenticated users
4. Connections CRUD works (create, read, update, delete)
5. Test connection button validates credentials
6. Forms have validation and error handling
7. UI is responsive and user-friendly
8. All MCP browser tests pass

## Rollback Plan

If frontend phase fails:
1. Keep backend unchanged (APIs still work)
2. Can access APIs via curl/Postman
3. Remove frontend/ directory changes
4. Use API docs at /docs as temporary UI
