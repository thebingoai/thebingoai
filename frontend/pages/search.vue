<template>
  <div class="container mx-auto p-6">
    <!-- Search Input -->
    <div class="mb-8">
      <SearchInput
        v-model="searchStore.query"
        :is-searching="isSearching"
        @search="performSearch"
      />
    </div>

    <!-- Main Content -->
    <div class="grid gap-6 lg:grid-cols-4">
      <!-- Sidebar -->
      <div class="space-y-6 lg:col-span-1">
        <FilterPanel
          v-model:top-k="searchStore.topK"
          v-model:min-score="searchStore.minScore"
          v-model:selected-namespaces="searchStore.namespaces"
          :available-namespaces="namespaceNames"
          @reset="resetFilters"
        />

        <SearchHistory
          :history="searchStore.history.slice(0, 10)"
          @select="selectHistory"
          @clear="searchStore.clearHistory()"
        />
      </div>

      <!-- Results -->
      <div class="lg:col-span-3">
        <!-- Loading State -->
        <div v-if="isSearching" class="space-y-4">
          <UiSkeleton v-for="i in 3" :key="i" height="120px" />
        </div>

        <!-- Error State -->
        <div v-else-if="error" class="rounded-lg border border-error-200 bg-error-50 p-6 dark:border-error-800 dark:bg-error-900/10">
          <p class="text-error-700 dark:text-error-400">
            {{ error }}
          </p>
        </div>

        <!-- Empty State -->
        <div v-else-if="!results">
          <UiEmptyState
            title="Start searching"
            description="Enter a query above to search your documents"
            :icon="Search"
          />
        </div>

        <!-- No Results -->
        <div v-else-if="results.total_results === 0">
          <UiEmptyState
            title="No results found"
            description="Try adjusting your search query or filters"
            :icon="Search"
          />
        </div>

        <!-- Results List -->
        <div v-else class="space-y-4">
          <div class="flex items-center justify-between">
            <p class="text-sm text-neutral-600 dark:text-neutral-400">
              Found {{ results.total_results }} results
            </p>
          </div>

          <div class="space-y-3">
            <ResultCard
              v-for="result in filteredResults"
              :key="result.id"
              :result="result"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Search } from 'lucide-vue-next'

const searchStore = useSearchStore()
const { namespaceNames } = useNamespaces()
const { search, isSearching, results, error } = useSearch()

const filteredResults = computed(() => {
  if (!results.value) return []
  return results.value.results.filter(r => r.score >= searchStore.minScore)
})

const performSearch = async () => {
  if (!searchStore.query.trim()) return

  const namespace = searchStore.namespaces.length === 1 ? searchStore.namespaces[0] : undefined

  await search({
    query: searchStore.query,
    namespace,
    top_k: searchStore.topK
  })
}

const selectHistory = (query: string) => {
  searchStore.setQuery(query)
  performSearch()
}

const resetFilters = () => {
  searchStore.resetFilters()
}
</script>
