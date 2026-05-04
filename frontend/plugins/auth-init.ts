export default defineNuxtPlugin(async () => {
  const authStore = useAuthStore()

  // Load SSO auth config from backend
  await authStore.loadAuthConfig()

  // Restore user session from localStorage
  try {
    await authStore.loadUser()
  } catch {
    // Session restore failed (e.g. inactive account) — start unauthenticated
  }
})
