<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
      <div>
        <h2 class="text-3xl font-bold text-center">Sign In</h2>
      </div>
      <form @submit.prevent="handleLogin" class="space-y-6">
        <div>
          <label class="block text-sm font-medium mb-2">Email</label>
          <input v-model="email" type="email" required
            class="w-full px-3 py-2 border rounded-md" />
        </div>
        <div>
          <label class="block text-sm font-medium mb-2">Password</label>
          <input v-model="password" type="password" required
            class="w-full px-3 py-2 border rounded-md" />
        </div>
        <button type="submit" :disabled="loading"
          class="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700">
          {{ loading ? 'Signing in...' : 'Sign In' }}
        </button>
      </form>
      <p class="text-center text-sm">
        Don't have an account?
        <NuxtLink to="/register" class="text-blue-600 hover:underline">Sign up</NuxtLink>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
const auth = useAuthNew()
const email = ref('')
const password = ref('')
const loading = computed(() => auth.loading.value)

async function handleLogin() {
  try {
    await auth.login({ email: email.value, password: password.value })
  } catch (error: any) {
    alert(error.message || 'Login failed')
  }
}

definePageMeta({
  layout: false
})
</script>
