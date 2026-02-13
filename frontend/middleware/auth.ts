export default defineNuxtRouteMiddleware(async (to) => {
  const authStore = useAuthStore()

  const publicRoutes = ['/login', '/register']

  // Load token and user from localStorage if not already loaded
  if (process.client) {
    if (!authStore.token) {
      const token = localStorage.getItem('auth_token')
      if (token) {
        authStore.token = token
      }
    }

    // Load user if we have a token but no user
    if (authStore.token && !authStore.user) {
      await authStore.fetchUser()
    }
  }

  // Redirect to login if not authenticated
  if (!authStore.isAuthenticated && !publicRoutes.includes(to.path)) {
    return navigateTo('/login')
  }

  // Redirect to chat if already authenticated
  if (authStore.isAuthenticated && publicRoutes.includes(to.path)) {
    return navigateTo('/chat')
  }
})
