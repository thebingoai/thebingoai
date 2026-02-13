import type { Memory, MemorySearchRequest, MemorySearchResponse } from '~/types/memory'

export const useMemoryNew = () => {
  const auth = useAuthNew()
  const memories = ref<Memory[]>([])
  const loading = ref(false)

  async function searchMemories(query: string, topK: number = 5) {
    loading.value = true
    try {
      const request: MemorySearchRequest = { query, top_k: topK }
      const response = await auth.apiRequest<MemorySearchResponse>('/api/memory/search', {
        method: 'POST',
        body: JSON.stringify(request)
      })
      memories.value = response.memories
      return response.memories
    } finally {
      loading.value = false
    }
  }

  async function generateMemory(date: string) {
    loading.value = true
    try {
      await auth.apiRequest('/api/memory/generate', {
        method: 'POST',
        body: JSON.stringify({ date })
      })
    } finally {
      loading.value = false
    }
  }

  async function deleteAllMemories() {
    if (!confirm('Delete all memories? This cannot be undone.')) return
    loading.value = true
    try {
      await auth.apiRequest('/api/memory', { method: 'DELETE' })
      memories.value = []
    } finally {
      loading.value = false
    }
  }

  return {
    memories,
    loading,
    searchMemories,
    generateMemory,
    deleteAllMemories
  }
}
