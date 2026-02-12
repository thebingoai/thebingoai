<template>
  <div class="relative">
    <div class="relative">
      <component
        :is="Search"
        class="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-neutral-400"
      />
      <input
        v-model="localQuery"
        type="text"
        placeholder="Search your documents..."
        class="h-14 w-full rounded-lg border border-neutral-300 bg-white pl-12 pr-24 text-lg transition-colors focus-ring dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
        @keydown.enter="handleSearch"
      />
      <UiButton
        class="absolute right-2 top-1/2 -translate-y-1/2"
        :loading="isSearching"
        :disabled="!localQuery.trim()"
        @click="handleSearch"
      >
        Search
      </UiButton>
    </div>

    <div v-if="showSuggestions && suggestions.length > 0" class="mt-2 flex flex-wrap gap-2">
      <button
        v-for="suggestion in suggestions"
        :key="suggestion"
        @click="selectSuggestion(suggestion)"
        class="rounded-full bg-neutral-100 px-3 py-1 text-sm text-neutral-700 transition-colors hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-700"
      >
        {{ suggestion }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Search } from 'lucide-vue-next'

interface Props {
  modelValue: string
  isSearching?: boolean
  showSuggestions?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isSearching: false,
  showSuggestions: true
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  search: []
}>()

const localQuery = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const suggestions = [
  'How to implement authentication?',
  'Explain the database schema',
  'What are the API endpoints?',
  'Show me the testing strategy'
]

const handleSearch = () => {
  if (localQuery.value.trim()) {
    emit('search')
  }
}

const selectSuggestion = (suggestion: string) => {
  emit('update:modelValue', suggestion)
  emit('search')
}
</script>
