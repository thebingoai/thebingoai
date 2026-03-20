export default defineNuxtPlugin(async () => {
  const authStore = useAuthStore()

  // Load auth provider config from backend (SSO vs Supabase)
  await authStore.loadAuthConfig()

  // Set up Supabase auth state listener (only when using Supabase)
  if (process.client && authStore.isSupabase) {
    try {
      const supabase = useSupabase()
      supabase.auth.onAuthStateChange((event, session) => {
        authStore.handleAuthStateChange(event, session)
      })
    } catch {
      // Supabase not configured — skip listener
    }
  }

  // Restore user session from localStorage
  await authStore.loadUser()
})
