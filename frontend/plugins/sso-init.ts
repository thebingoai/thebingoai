export default defineNuxtPlugin(async () => {
  const authStore = useAuthStore()

  // Load SSO config first (needed for loginWithGoogle)
  await authStore.loadSSOConfig()

  // Then restore user session from localStorage
  await authStore.loadUser()
})
