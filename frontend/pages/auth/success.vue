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
  const accessToken = route.query.access_token as string
  const refreshToken = route.query.refresh_token as string
  const isFirstLogin = route.query.is_first_login === 'true'

  if (accessToken && refreshToken) {
    await authStore.handleOAuthSuccess(accessToken, refreshToken, isFirstLogin)
    router.push(authStore.isFirstLogin ? '/connect' : '/chat')
  } else {
    router.push('/auth/error?reason=missing_tokens')
  }
})

definePageMeta({
  layout: false
})
</script>
