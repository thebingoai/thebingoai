<template>
  <div class="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
    <div class="mb-4 flex items-center justify-between">
      <h3 class="font-semibold text-neutral-900 dark:text-neutral-100">
        Recent Searches
      </h3>
      <button
        v-if="history.length > 0"
        @click="$emit('clear')"
        class="text-sm text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300"
      >
        Clear
      </button>
    </div>

    <div v-if="history.length === 0" class="text-center py-4">
      <p class="text-sm text-neutral-500 dark:text-neutral-400">
        No recent searches
      </p>
    </div>

    <div v-else class="space-y-2">
      <button
        v-for="item in history"
        :key="item.id"
        @click="$emit('select', item.query)"
        class="flex w-full items-start justify-between rounded-lg p-2 text-left transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-800"
      >
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium text-neutral-900 dark:text-neutral-100">
            {{ item.query }}
          </p>
          <p class="mt-0.5 text-xs text-neutral-500 dark:text-neutral-400">
            {{ item.results_count }} results · {{ timeAgo(item.timestamp) }}
          </p>
        </div>
        <component :is="Clock" class="ml-2 h-4 w-4 flex-shrink-0 text-neutral-400" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Clock } from 'lucide-vue-next'
import type { SearchHistoryItem } from '~/types'
import { timeAgo } from '~/utils/format'

interface Props {
  history: SearchHistoryItem[]
}

defineProps<Props>()

defineEmits<{
  select: [query: string]
  clear: []
}>()
</script>
