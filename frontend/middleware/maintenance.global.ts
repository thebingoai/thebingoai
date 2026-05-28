// Global maintenance gate. Runs on EVERY route (including public ones like
// /login and /register) because `middleware/auth.ts` is opt-in via
// definePageMeta and would never fire on the login page itself — which is
// precisely what we need to hide during maintenance.
//
// State is sourced from the Pinia auth store, which the auth-init.ts plugin
// populates via /api/auth/config before any middleware runs. The cookie that
// drives `bypass_active` is HttpOnly, so the frontend only sees the resolved
// boolean — never the key.
export default defineNuxtRouteMiddleware((to) => {
  const authStore = useAuthStore()

  // Maintenance ON + no bypass → everyone lands on /maintenance.
  if (authStore.maintenance.active && !authStore.maintenance.bypass_active) {
    if (to.path !== '/maintenance') return navigateTo('/maintenance')
    return
  }

  // Maintenance OFF → /maintenance is no longer a real destination; send home.
  if (!authStore.maintenance.active && to.path === '/maintenance') {
    return navigateTo('/')
  }
})
