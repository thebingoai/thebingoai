<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="max-w-md w-full p-8 bg-white rounded-lg shadow-md text-center">
      <p class="text-gray-600">Signing you in...</p>
    </div>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

onMounted(async () => {
  if (authStore.isSupabase) {
    // Supabase OAuth: tokens are in URL hash, processed by onAuthStateChange
    try {
      const supabase = useSupabase()
      const { data, error } = await supabase.auth.getSession()

      if (error || !data.session) {
        await new Promise(resolve => setTimeout(resolve, 1000))
        const retry = await supabase.auth.getSession()
        if (retry.data.session) {
          authStore.token = retry.data.session.access_token
          localStorage.setItem('auth_token', retry.data.session.access_token)
          await authStore.fetchUser()
          router.push('/chat')
          return
        }
        router.push('/auth/error?reason=no_session')
        return
      }

      authStore.token = data.session.access_token
      localStorage.setItem('auth_token', data.session.access_token)
      await authStore.fetchUser()
      router.push('/chat')
    } catch {
      router.push('/auth/error?reason=oauth_error')
    }
  } else {
    // SSO: tokens come as query params
    const accessToken = route.query.access_token as string
    const refreshToken = route.query.refresh_token as string

    if (accessToken && refreshToken) {
      await authStore.handleOAuthSuccess(accessToken, refreshToken)
      router.push('/chat')
    } else {
      router.push('/auth/error?reason=missing_tokens')
    }
  }
})

definePageMeta({
  layout: false
})
</script>
