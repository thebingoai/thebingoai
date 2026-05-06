<template>
  <!-- Error -->
  <div
    v-if="error"
    class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400"
  >
    {{ error }}
  </div>

  <!-- Loading skeletons -->
  <div v-if="loading" class="space-y-3">
    <UiSkeleton class="h-24 w-full rounded-lg" />
    <UiSkeleton class="h-24 w-full rounded-lg" />
    <UiSkeleton class="h-24 w-full rounded-lg" />
  </div>

  <!-- Empty state -->
  <UiEmptyState
    v-else-if="items.length === 0"
    :title="`No ${itemLabel}s yet`"
    :description="`Create a ${itemLabel} to get started.`"
  />

  <!-- Item list -->
  <div v-else class="space-y-3">
    <UiCard
      v-for="item in items"
      :key="item.id"
      class="px-5 py-4 cursor-pointer hover:shadow-lg transition-shadow"
      @click="$emit('select', item.id)"
    >
      <div class="flex items-start justify-between gap-4">
        <!-- Left: name + meta -->
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-sm font-medium text-gray-900 dark:text-neutral-100 truncate">
              {{ item.name }}
            </span>
            <UiBadge :variant="statusVariant(item.last_run_status)" size="sm" :dot="true">
              {{ statusLabel(item.last_run_status) }}
            </UiBadge>
            <UiBadge v-if="item.enabled === false" variant="warning" size="sm">Disabled</UiBadge>
          </div>

          <div class="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-neutral-400">
            <span v-if="item.cron" class="flex items-center gap-1">
              <Clock class="h-3 w-3" />
              {{ item.cron }}
            </span>
            <span v-else class="flex items-center gap-1 italic">
              <Clock class="h-3 w-3" />
              Manual only
            </span>
          </div>

          <div v-if="item.last_run_at" class="mt-1 text-xs text-gray-400 dark:text-neutral-500">
            Last run {{ formatRelative(item.last_run_at) }}
            <template v-if="item.next_run_at">
              · Next {{ formatRelative(item.next_run_at) }}
            </template>
          </div>
        </div>

        <!-- Right: slot for action buttons -->
        <div class="shrink-0 flex items-center gap-2">
          <slot name="actions" :item="item" />
        </div>
      </div>
    </UiCard>
  </div>
</template>

<script setup lang="ts">
import { Clock } from 'lucide-vue-next'

export interface ScheduledJob {
  id: string
  name: string
  last_run_status?: string | null
  last_run_at?: string | null
  next_run_at?: string | null
  cron?: string | null
  enabled?: boolean
}

interface Props {
  items: ScheduledJob[]
  loading?: boolean
  error?: string | null
  itemLabel?: string
}

withDefaults(defineProps<Props>(), {
  loading: false,
  error: null,
  itemLabel: 'item',
})

defineEmits<{
  select: [id: string]
}>()

function statusVariant(status?: string | null): 'success' | 'error' | 'info' | 'default' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'running') return 'info'
  return 'default'
}

function statusLabel(status?: string | null): string {
  if (status === 'success') return 'Success'
  if (status === 'failed') return 'Failed'
  if (status === 'running') return 'Running'
  return 'Never run'
}

function formatRelative(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.round(diffMs / 1000)
  if (diffSec < 60) return 'just now'
  const diffMin = Math.round(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.round(diffHr / 24)
  if (diffDay < 30) return `${diffDay}d ago`
  return date.toLocaleDateString()
}
</script>
