<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
      <div>
        <h2 class="text-3xl font-bold text-center">Create Account</h2>
      </div>
      <form @submit.prevent="handleRegister" class="space-y-6">
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
          {{ loading ? 'Creating account...' : 'Sign Up' }}
        </button>
      </form>
      <p class="text-center text-sm">
        Already have an account?
        <NuxtLink to="/login" class="text-blue-600 hover:underline">Sign in</NuxtLink>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
const auth = useAuthNew()
const email = ref('')
const password = ref('')
const loading = computed(() => auth.loading.value)

async function handleRegister() {
  try {
    await auth.register({ email: email.value, password: password.value })
  } catch (error: any) {
    alert(error.message || 'Registration failed')
  }
}

definePageMeta({
  layout: false
})
</script>
