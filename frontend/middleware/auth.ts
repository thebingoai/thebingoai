export default defineNuxtRouteMiddleware(async (to) => {
  const authStore = useAuthStore()

  // Maintenance gate: when maintenance_mode is on, only callers with a valid
  // bypass cookie may reach normal routes. Everyone else lands on /maintenance.
  // Populated by auth-init.ts plugin via /api/auth/config before this runs.
  if (authStore.maintenance.active && !authStore.maintenance.bypass_active) {
    if (to.path !== '/maintenance') return navigateTo('/maintenance')
    return
  }
  // Inverse: when maintenance is off, /maintenance is not a real destination.
  if (!authStore.maintenance.active && to.path === '/maintenance') {
    return navigateTo('/')
  }

  const publicRoutes = ['/login', '/register', '/auth/verify', '/auth/success', '/auth/error', '/auth/forgot-password', '/auth/reset-password', '/verify-account', '/reset-password']
  // Token-exchange routes must not redirect authenticated users — a token is being
  // consumed to switch identity. This includes OAuth callbacks AND the email-verify
  // pages: clicking a verification link in a browser with a stale session must let the
  // verify page mount and swap to the new account instead of bouncing to /chat as the
  // old user.
  const oauthCallbackRoutes = ['/auth/success', '/auth/error', '/auth/verify', '/verify-account']

  // Load token from localStorage if not already loaded
  if (process.client) {
    if (!authStore.token) {
      const token = localStorage.getItem('auth_token')
      if (token) {
        authStore.token = token
      }
    }

    // If token exists but user is not yet loaded, await fetchUser() before
    // performing any redirect. This prevents a flash where the user sees /connect
    // briefly before auth middleware redirects to /login (or vice versa).
    if (authStore.token && !authStore.user) {
      await authStore.fetchUser()
    }
  }

  // Redirect to login if not authenticated
  if (!authStore.isAuthenticated && !publicRoutes.includes(to.path)) {
    return navigateTo('/login')
  }

  // Redirect to chat if already authenticated (but not on OAuth callback routes)
  if (authStore.isAuthenticated && publicRoutes.includes(to.path) && !oauthCallbackRoutes.includes(to.path)) {
    return navigateTo('/chat')
  }
})
