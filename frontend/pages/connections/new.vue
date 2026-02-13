<template>
  <div class="p-8 max-w-2xl mx-auto">
    <h1 class="text-3xl font-bold mb-6">Add Database Connection</h1>

    <form @submit.prevent="handleSubmit" class="space-y-4">
      <div>
        <label class="block text-sm font-medium mb-2">Name</label>
        <input v-model="form.name" required class="w-full px-3 py-2 border rounded-md" />
      </div>

      <div>
        <label class="block text-sm font-medium mb-2">Database Type</label>
        <select v-model="form.db_type" required class="w-full px-3 py-2 border rounded-md">
          <option value="postgres">PostgreSQL</option>
          <option value="mysql">MySQL</option>
        </select>
      </div>

      <div>
        <label class="block text-sm font-medium mb-2">Host</label>
        <input v-model="form.host" required class="w-full px-3 py-2 border rounded-md" />
      </div>

      <div>
        <label class="block text-sm font-medium mb-2">Port</label>
        <input v-model.number="form.port" type="number" required class="w-full px-3 py-2 border rounded-md" />
      </div>

      <div>
        <label class="block text-sm font-medium mb-2">Database</label>
        <input v-model="form.database" required class="w-full px-3 py-2 border rounded-md" />
      </div>

      <div>
        <label class="block text-sm font-medium mb-2">Username</label>
        <input v-model="form.username" required class="w-full px-3 py-2 border rounded-md" />
      </div>

      <div>
        <label class="block text-sm font-medium mb-2">Password</label>
        <input v-model="form.password" type="password" required class="w-full px-3 py-2 border rounded-md" />
      </div>

      <div class="flex gap-4">
        <button type="submit" :disabled="loading"
          class="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700">
          {{ loading ? 'Creating...' : 'Create Connection' }}
        </button>
        <NuxtLink to="/connections"
          class="bg-gray-200 px-6 py-2 rounded-md hover:bg-gray-300">
          Cancel
        </NuxtLink>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import type { ConnectionFormData } from '~/types/connection'

definePageMeta({
  middleware: 'auth'
})

const auth = useAuthNew()
const router = useRouter()
const loading = ref(false)

const form = ref<ConnectionFormData>({
  name: '',
  db_type: 'postgres' as any,
  host: 'localhost',
  port: 5432,
  database: '',
  username: '',
  password: ''
})

async function handleSubmit() {
  loading.value = true
  try {
    await auth.apiRequest('/api/connections', {
      method: 'POST',
      body: JSON.stringify(form.value)
    })
    router.push('/connections')
  } catch (error: any) {
    alert(error.message || 'Failed to create connection')
  } finally {
    loading.value = false
  }
}
</script>
