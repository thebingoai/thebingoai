<template>
  <div class="p-8">
    <h1 class="text-3xl font-bold mb-6">Memory Insights</h1>

    <div class="mb-6 space-y-4">
      <div class="flex gap-4">
        <input v-model="searchQuery" placeholder="Search memories..."
          class="flex-1 px-4 py-2 border rounded-md" />
        <button @click="handleSearch" :disabled="memory.loading.value"
          class="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50">
          {{ memory.loading.value ? 'Searching...' : 'Search' }}
        </button>
      </div>

      <button @click="memory.deleteAllMemories()"
        class="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700">
        Delete All Memories
      </button>
    </div>

    <div v-if="memory.loading.value" class="text-center py-8">Loading...</div>

    <div v-else-if="memory.memories.value.length === 0"
      class="text-center py-8 text-gray-500">
      No memories found. Search to find relevant memories.
    </div>

    <div v-else class="space-y-4">
      <div v-for="mem in memory.memories.value" :key="mem.id"
        class="p-4 border rounded-lg hover:shadow-md transition">
        <div class="flex justify-between items-start mb-2">
          <div class="text-sm text-gray-600">{{ mem.date }}</div>
          <div class="text-sm font-semibold">Score: {{ (mem.score * 100).toFixed(1) }}%</div>
        </div>
        <p class="text-gray-800">{{ mem.text }}</p>
        <div v-if="Object.keys(mem.metadata).length > 0" class="mt-2 text-sm text-gray-600">
          <span v-for="(value, key) in mem.metadata" :key="key" class="mr-4">
            {{ key }}: {{ value }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: 'auth'
})

const memory = useMemoryNew()
const searchQuery = ref('')

async function handleSearch() {
  if (!searchQuery.value.trim()) return
  try {
    await memory.searchMemories(searchQuery.value)
  } catch (error: any) {
    alert(error.message || 'Search failed')
  }
}
</script>
