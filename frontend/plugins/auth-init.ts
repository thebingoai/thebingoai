export default defineNuxtPlugin(async () => {
  const authStore = useAuthStore()

  // Load SSO auth config from backend
  await authStore.loadAuthConfig()

  // Restore user session from localStorage
  await authStore.loadUser()
})
