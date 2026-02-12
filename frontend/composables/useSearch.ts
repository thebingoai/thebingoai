import type { QueryRequest, QueryResponse, SearchHistoryItem } from '~/types'
import { toast } from 'vue-sonner'
import { MESSAGES } from '~/utils/constants'

export const useSearch = () => {
  const api = useApi()
  const searchStore = useSearchStore()

  const isSearching = ref(false)
  const results = ref<QueryResponse | null>(null)
  const error = ref<string | null>(null)

  const search = async (request: QueryRequest) => {
    isSearching.value = true
    error.value = null

    try {
      const response = await api.query(request)
      results.value = response

      // Add to search history
      const historyItem: SearchHistoryItem = {
        id: `${Date.now()}-${Math.random()}`,
        query: request.query,
        namespace: request.namespace,
        results_count: response.total_results,
        timestamp: new Date().toISOString()
      }
      searchStore.addToHistory(historyItem)

      return response
    } catch (err: any) {
      error.value = err.message || MESSAGES.SEARCH_ERROR
      toast.error(error.value || 'Search failed')
      throw err
    } finally {
      isSearching.value = false
    }
  }

  const clearResults = () => {
    results.value = null
    error.value = null
  }

  return {
    isSearching: readonly(isSearching),
    results: readonly(results),
    error: readonly(error),
    search,
    clearResults
  }
}
