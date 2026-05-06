<template>
  <div v-if="loading" class="space-y-2">
    <UiSkeleton class="h-12 w-full rounded-lg" />
    <UiSkeleton class="h-12 w-full rounded-lg" />
    <UiSkeleton class="h-12 w-full rounded-lg" />
  </div>

  <UiEmptyState
    v-else-if="runs.length === 0"
    title="No runs yet"
    description="Trigger a manual run or wait for the cron schedule to fire."
  />

  <div v-else class="space-y-2">
    <div
      v-for="run in runs"
      :key="run.id"
      class="rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-4 py-3 flex items-start justify-between gap-4"
    >
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2 flex-wrap">
          <UiBadge :variant="runStatusVariant(run.status)" size="sm" :dot="true">
            {{ run.status }}
          </UiBadge>
          <span class="text-xs text-gray-500 dark:text-neutral-400">
            {{ formatDate(run.started_at) }}
          </span>
          <UiBadge variant="default" size="sm">{{ run.triggered_by }}</UiBadge>
        </div>

        <div
          v-if="run.error_message"
          class="mt-1.5 text-xs text-red-600 dark:text-red-400 font-mono truncate"
        >
          {{ run.error_message }}
        </div>
      </div>

      <div class="shrink-0 text-right text-xs text-gray-500 dark:text-neutral-400">
        <div v-if="run.rows_written !== null && run.rows_written !== undefined">
          {{ run.rows_written.toLocaleString() }} rows
        </div>
        <div v-if="run.finished_at && run.started_at">
          {{ formatDuration(run.started_at, run.finished_at) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
export interface RunRecord {
  id: string
  status: string
  started_at: string
  finished_at?: string | null
  triggered_by: string
  error_message?: string | null
  rows_written?: number | null
}

interface Props {
  runs: RunRecord[]
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  loading: false,
})

function runStatusVariant(status: string): 'success' | 'error' | 'info' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'error'
  return 'info'
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

function formatDuration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime()
  const sec = Math.round(ms / 1000)
  if (sec < 60) return `${sec}s`
  const min = Math.floor(sec / 60)
  const rem = sec % 60
  return `${min}m ${rem}s`
}
</script>
