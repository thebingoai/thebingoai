<template>
  <div class="rounded-lg border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900">
    <h2 class="mb-4 text-lg font-semibold text-neutral-900 dark:text-neutral-100">
      System Status
    </h2>

    <div v-if="loading" class="space-y-3">
      <div v-for="i in 3" :key="i" class="flex items-center justify-between">
        <UiSkeleton width="100px" height="16px" />
        <UiSkeleton width="60px" height="20px" />
      </div>
    </div>

    <div v-else class="space-y-3">
      <div class="flex items-center justify-between">
        <span class="text-sm text-neutral-700 dark:text-neutral-300">API</span>
        <UiBadge :variant="getStatusVariant(health?.checks?.api)" dot>
          {{ health?.checks?.api || 'Unknown' }}
        </UiBadge>
      </div>

      <div class="flex items-center justify-between">
        <span class="text-sm text-neutral-700 dark:text-neutral-300">Redis</span>
        <UiBadge :variant="getStatusVariant(health?.checks?.redis)" dot>
          {{ health?.checks?.redis || 'Unknown' }}
        </UiBadge>
      </div>

      <div class="flex items-center justify-between">
        <span class="text-sm text-neutral-700 dark:text-neutral-300">Pinecone</span>
        <UiBadge :variant="getStatusVariant(health?.checks?.pinecone)" dot>
          {{ health?.checks?.pinecone || 'Unknown' }}
        </UiBadge>
      </div>

      <div v-if="health?.checks?.pinecone_vectors !== undefined" class="pt-3 border-t border-neutral-200 dark:border-neutral-800">
        <div class="flex items-center justify-between">
          <span class="text-sm text-neutral-700 dark:text-neutral-300">Total Vectors</span>
          <span class="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
            {{ health.checks.pinecone_vectors.toLocaleString() }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DetailedHealthResponse } from '~/types'

interface Props {
  health?: DetailedHealthResponse
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  loading: false
})

const getStatusVariant = (status?: string): 'success' | 'warning' | 'error' | 'default' => {
  if (!status) return 'default'
  if (status.toLowerCase() === 'healthy' || status.toLowerCase() === 'ok') return 'success'
  if (status.toLowerCase() === 'degraded') return 'warning'
  if (status.toLowerCase() === 'unhealthy' || status.toLowerCase().includes('error')) return 'error'
  return 'default'
}
</script>
