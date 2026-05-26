<template>
  <div class="mt-auto border-t border-gray-100 dark:border-neutral-600 pt-2.5 flex items-center gap-3 flex-wrap">
    <!-- Slot 1: profiling status (always) -->
    <div class="flex flex-col items-center gap-1" :title="statusTitle">
      <component :is="status.icon" :class="['h-3.5 w-3.5', status.color, status.spin ? 'animate-spin' : '']" />
      <span :class="['text-[10px]', status.color]">{{ status.label }}</span>
    </div>

    <!-- Slot 2: SSL (only when enabled) -->
    <div v-if="connection.ssl_enabled" class="flex flex-col items-center gap-1" title="SSL Enabled">
      <Shield class="h-3.5 w-3.5 text-gray-500 dark:text-neutral-300" />
      <span class="text-[10px] text-gray-500 dark:text-neutral-300">SSL</span>
    </div>

    <!-- Slot 3: table count (only when profile success) -->
    <div
      v-if="connection.profiling_status === 'ready' && connection.table_count != null"
      class="flex flex-col items-center gap-1"
      :title="`${connection.table_count} tables`"
    >
      <Table2 class="h-3.5 w-3.5 text-gray-500 dark:text-neutral-300" />
      <span class="text-[10px] text-gray-500 dark:text-neutral-300">{{ connection.table_count }} tables</span>
    </div>

    <!-- Slot 4: time-ago (always; label depends on status) -->
    <div class="flex flex-col items-center gap-1" :title="timeTitle">
      <Clock class="h-3.5 w-3.5 text-gray-500 dark:text-neutral-300" />
      <span class="text-[10px] text-gray-500 dark:text-neutral-300">{{ timeLabel }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Activity, Clock, Loader2, Shield, Table2, XCircle } from 'lucide-vue-next'
import type { DatabaseConnection } from '~/types/connection'
import { parseUtcDate } from '~/utils/format'

const props = defineProps<{ connection: DatabaseConnection }>()

type StatusSlot = {
  icon: any
  label: 'Healthy' | 'Error' | 'Profiling' | 'Unknown'
  color: string
  spin?: boolean
}

const status = computed<StatusSlot>(() => {
  switch (props.connection.profiling_status) {
    case 'ready':
      return { icon: Activity, label: 'Healthy', color: 'text-green-600' }
    case 'failed':
      return { icon: XCircle, label: 'Error', color: 'text-red-500' }
    case 'in_progress':
    case 'pending':
      return { icon: Loader2, label: 'Profiling', color: 'text-purple-600', spin: true }
    default:
      return { icon: Activity, label: 'Unknown', color: 'text-gray-400' }
  }
})

const statusTitle = computed(() => {
  const s = props.connection.profiling_status
  if (s === 'ready') return 'Profiling complete'
  if (s === 'failed') return props.connection.profiling_error || 'Profiling failed'
  if (s === 'in_progress') return props.connection.profiling_progress || 'Profiling in progress'
  if (s === 'pending') return props.connection.profiling_progress || 'Profiling queued'
  return 'Profiling status unknown'
})

function formatRelative(dateString: string): string {
  const date = parseUtcDate(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 30) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

const timeLabel = computed(() => {
  const s = props.connection.profiling_status
  if (s === 'in_progress' || s === 'pending') return 'Profiling'
  if (props.connection.profiling_started_at) return formatRelative(props.connection.profiling_started_at)
  return '—'
})

const timeTitle = computed(() => {
  const s = props.connection.profiling_status
  if (s === 'in_progress' || s === 'pending') return 'Profiling in progress'
  if (props.connection.profiling_started_at) {
    return `Profile started ${formatRelative(props.connection.profiling_started_at)}`
  }
  return 'No profile run yet'
})
</script>
