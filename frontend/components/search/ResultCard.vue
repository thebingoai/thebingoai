<template>
  <div class="rounded-lg border border-neutral-200 bg-white p-4 transition-all hover:shadow-md dark:border-neutral-800 dark:bg-neutral-900">
    <!-- Header -->
    <div class="mb-3 flex items-start justify-between">
      <div class="flex items-center gap-2">
        <component :is="FileText" class="h-4 w-4 text-neutral-400" />
        <span class="font-medium text-neutral-900 dark:text-neutral-100">
          {{ result.source }}
        </span>
      </div>
      <UiBadge :variant="getScoreVariant(result.score)" size="sm">
        {{ (result.score * 100).toFixed(0) }}%
      </UiBadge>
    </div>

    <!-- Content -->
    <p class="mb-3 line-clamp-3 text-sm text-neutral-700 dark:text-neutral-300">
      {{ result.text }}
    </p>

    <!-- Footer -->
    <div class="flex items-center justify-between text-xs text-neutral-500">
      <span>Chunk {{ result.chunk_index }}</span>
      <span v-if="result.created_at">
        {{ timeAgo(result.created_at) }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { FileText } from 'lucide-vue-next'
import type { QueryResult } from '~/types'
import { timeAgo } from '~/utils/format'
import { getScoreRange } from '~/utils/score'

interface Props {
  result: QueryResult
}

const props = defineProps<Props>()

const getScoreVariant = (score: number): 'success' | 'primary' | 'warning' | 'default' => {
  const range = getScoreRange(score)
  const variants = {
    excellent: 'success' as const,
    good: 'primary' as const,
    fair: 'warning' as const,
    low: 'default' as const
  }
  return variants[range]
}
</script>
