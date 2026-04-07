<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="max-w-md w-full p-8 bg-white rounded-lg shadow-md">
      <div class="mb-8">
        <h2 class="text-3xl font-medium text-center text-gray-900">Sign Up</h2>
      </div>

      <div v-if="error" class="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
        {{ error }}
      </div>

      <form @submit.prevent="handleRegister" class="space-y-6">
        <UiInput
          v-model="email"
          type="email"
          label="Email"
          placeholder="you@example.com"
          required
        />

        <UiInput
          v-model="password"
          type="password"
          label="Password"
          placeholder="••••••••"
          required
        />

        <UiButton
          type="submit"
          variant="primary"
          :loading="loading"
          :disabled="loading"
          full-width
        >
          Sign Up
        </UiButton>
      </form>

      <template v-if="authStore.hasGoogleOAuth">
        <div class="relative my-6">
          <div class="absolute inset-0 flex items-center">
            <div class="w-full border-t border-gray-200"></div>
          </div>
          <div class="relative flex justify-center text-sm">
            <span class="px-2 bg-white text-gray-500">or</span>
          </div>
        </div>

        <UiButton
          type="button"
          variant="secondary"
          :disabled="loading"
          full-width
          @click="handleGoogleSignup"
        >
          Continue with Google
        </UiButton>
      </template>

      <p class="mt-6 text-center text-sm text-gray-500">
        Already have an account?
        <NuxtLink to="/login" class="text-gray-900 hover:underline font-light">Sign in</NuxtLink>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const router = useRouter()

const email = ref('')
const password = ref('')
const loading = computed(() => authStore.loading)
const error = computed(() => authStore.error)

async function handleRegister() {
  const result = await authStore.register(email.value, password.value)
  if (result.success) {
    router.push('/auth/verify')
  }
}

function handleGoogleSignup() {
  authStore.loginWithGoogle()
}

definePageMeta({
  layout: false
})
</script>
