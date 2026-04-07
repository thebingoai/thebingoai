<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="max-w-md w-full p-8 bg-white rounded-lg shadow-md text-center">
      <div v-if="verifying">
        <p class="text-gray-600">Verifying your email...</p>
      </div>

      <div v-else-if="verified">
        <h2 class="text-2xl font-medium text-gray-900 mb-4">Email Verified!</h2>
        <p class="text-gray-600 mb-6">Your email has been verified. Redirecting...</p>
      </div>

      <div v-else>
        <h2 class="text-2xl font-medium text-gray-900 mb-4">Check your email</h2>
        <p class="text-gray-600 mb-2">
          We sent a verification link to
        </p>
        <p v-if="pendingEmail" class="font-medium text-gray-900 mb-6">{{ pendingEmail }}</p>
        <p v-else class="font-medium text-gray-900 mb-6">your email address</p>
        <p class="text-sm text-gray-500 mb-6">
          Click the link in the email to verify your account.
        </p>

        <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {{ error }}
        </div>

        <div v-if="resendSuccess" class="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-600">
          Verification email resent!
        </div>

        <UiButton
          v-if="pendingEmail"
          variant="secondary"
          :loading="resending"
          :disabled="resending"
          full-width
          @click="handleResend"
        >
          Resend verification email
        </UiButton>

        <p class="mt-4 text-sm text-gray-500">
          <NuxtLink to="/login" class="text-gray-900 hover:underline">Back to sign in</NuxtLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const verifying = ref(false)
const verified = ref(false)
const resending = ref(false)
const resendSuccess = ref(false)
const error = ref('')
const pendingEmail = ref('')

onMounted(async () => {
  const token = route.query.token as string
  if (token) {
    verifying.value = true
    const result = await authStore.verifyEmail(token)
    verifying.value = false
    if (result.success) {
      verified.value = true
      setTimeout(() => router.push('/chat'), 1500)
    } else {
      error.value = result.error || 'Verification failed. Please try again.'
    }
  }
})

async function handleResend() {
  if (!pendingEmail.value) return
  resending.value = true
  resendSuccess.value = false
  error.value = ''
  const result = await authStore.resendVerification(pendingEmail.value)
  resending.value = false
  if (result.success) {
    resendSuccess.value = true
  } else {
    error.value = result.error || 'Failed to resend. Please try again.'
  }
}

definePageMeta({
  layout: false
})
</script>
