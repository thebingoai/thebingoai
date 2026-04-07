<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="max-w-md w-full p-8 bg-white rounded-lg shadow-md">
      <div class="mb-8">
        <h2 class="text-3xl font-medium text-center text-gray-900">Sign In</h2>
      </div>

      <div v-if="error" class="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
        {{ error }}
      </div>

      <form @submit.prevent="handleLogin" class="space-y-6">
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
          Sign In
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
          @click="handleGoogleLogin"
        >
          Continue with Google
        </UiButton>
      </template>

      <div class="mt-4 text-center">
        <NuxtLink to="/auth/forgot-password" class="text-sm text-gray-500 hover:underline">
          Forgot password?
        </NuxtLink>
      </div>

      <p class="mt-4 text-center text-sm text-gray-500">
        Don't have an account?
        <NuxtLink to="/register" class="text-gray-900 hover:underline font-light">Sign up</NuxtLink>
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

async function handleLogin() {
  const result = await authStore.login({ email: email.value, password: password.value })
  if (result.success) {
    router.push('/chat')
  }
}

function handleGoogleLogin() {
  authStore.loginWithGoogle()
}

definePageMeta({
  layout: false
})
</script>
