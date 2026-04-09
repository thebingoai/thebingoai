<template>
  <div class="flex items-center justify-center min-h-screen bg-gray-50">
    <div class="text-center space-y-4 p-8">
      <template v-if="error">
        <div class="text-red-600 text-lg font-medium">{{ error }}</div>
        <p class="text-sm text-gray-500">You can close this window and try again.</p>
      </template>
      <template v-else>
        <div class="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto" />
        <p class="text-sm text-gray-600">Connecting to Facebook...</p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: false, auth: false })

const route = useRoute()
const error = ref('')

onMounted(async () => {
  const code = route.query.code as string
  const state = route.query.state as string

  if (!code || !state) {
    error.value = 'Missing authorization parameters.'
    return
  }

  try {
    const data = await $fetch<{ accounts: any[]; token_ref: string }>(
      '/api/facebook-ads/auth/callback',
      { params: { code, state } },
    )

    if (window.opener) {
      window.opener.postMessage(
        { type: 'facebook-oauth-callback', accounts: data.accounts, token_ref: data.token_ref },
        window.location.origin,
      )
      window.close()
    } else {
      // Direct navigation — redirect to settings
      navigateTo('/settings')
    }
  } catch (err: any) {
    error.value = err?.data?.detail || err?.message || 'Failed to connect with Facebook.'
    if (window.opener) {
      window.opener.postMessage(
        { type: 'facebook-oauth-callback', error: error.value },
        window.location.origin,
      )
    }
  }
})
</script>
