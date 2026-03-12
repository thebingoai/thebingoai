<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="max-w-md w-full p-8 bg-white rounded-lg shadow-md text-center">
      <h2 class="text-2xl font-medium text-gray-900 mb-4">Authentication Failed</h2>
      <p class="text-gray-600 mb-6">{{ errorMessage }}</p>
      <UiButton variant="primary" full-width @click="tryAgain">
        Try Again
      </UiButton>
    </div>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const router = useRouter()

const errorMessages: Record<string, string> = {
  missing_tokens: 'Authentication tokens were not received.',
  access_denied: 'Access was denied.',
  default: 'Something went wrong during authentication.',
}

const errorMessage = computed(() => {
  const reason = route.query.reason as string
  return errorMessages[reason] || route.query.message as string || errorMessages.default
})

function tryAgain() {
  router.push('/login')
}

definePageMeta({
  layout: false
})
</script>
