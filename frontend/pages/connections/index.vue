<template>
  <div class="p-8">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold">Database Connections</h1>
      <NuxtLink to="/connections/new"
        class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
        Add Connection
      </NuxtLink>
    </div>

    <div v-if="loading" class="text-center py-8">Loading...</div>

    <div v-else-if="connections.length === 0" class="text-center py-8 text-gray-500">
      No connections yet. Create one to get started.
    </div>

    <div v-else class="grid gap-4">
      <div v-for="conn in connections" :key="conn.id"
        class="p-4 border rounded-lg hover:shadow-md transition">
        <div class="flex justify-between items-start">
          <div>
            <h3 class="font-semibold text-lg">{{ conn.name }}</h3>
            <p class="text-sm text-gray-600">{{ conn.db_type }} - {{ conn.host }}:{{ conn.port }}</p>
            <p class="text-sm text-gray-500">Database: {{ conn.database }}</p>
          </div>
          <button @click="deleteConnection(conn.id)"
            class="text-red-600 hover:text-red-800">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DatabaseConnection } from '~/types/connection'

definePageMeta({
  middleware: 'auth'
})

const auth = useAuthNew()
const connections = ref<DatabaseConnection[]>([])
const loading = ref(true)

onMounted(async () => {
  await loadConnections()
})

async function loadConnections() {
  try {
    connections.value = await auth.apiRequest<DatabaseConnection[]>('/api/connections')
  } catch (error: any) {
    console.error('Failed to load connections:', error)
  } finally {
    loading.value = false
  }
}

async function deleteConnection(id: number) {
  if (!confirm('Delete this connection?')) return
  try {
    await auth.apiRequest(`/api/connections/${id}`, { method: 'DELETE' })
    await loadConnections()
  } catch (error: any) {
    alert(error.message || 'Failed to delete')
  }
}
</script>
