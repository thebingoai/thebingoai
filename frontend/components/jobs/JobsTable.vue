<template>
  <div class="overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800">
    <div class="overflow-x-auto">
      <table class="w-full">
        <thead class="border-b border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-900">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-neutral-700 dark:text-neutral-300">
              File
            </th>
            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-neutral-700 dark:text-neutral-300">
              Namespace
            </th>
            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-neutral-700 dark:text-neutral-300">
              Status
            </th>
            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-neutral-700 dark:text-neutral-300">
              Progress
            </th>
            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-neutral-700 dark:text-neutral-300">
              Created
            </th>
            <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-neutral-700 dark:text-neutral-300">
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-neutral-200 dark:divide-neutral-800">
          <tr
            v-for="job in jobs"
            :key="job.job_id"
            class="transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-900"
          >
            <td class="px-4 py-3 text-sm font-medium text-neutral-900 dark:text-neutral-100">
              {{ job.file_name }}
            </td>
            <td class="px-4 py-3 text-sm text-neutral-600 dark:text-neutral-400">
              {{ job.namespace }}
            </td>
            <td class="px-4 py-3">
              <UiBadge :variant="getStatusVariant(job.status)" size="sm" dot>
                {{ job.status }}
              </UiBadge>
            </td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <div class="h-2 w-24 overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
                  <div
                    class="h-full transition-all"
                    :class="getProgressColor(job.status)"
                    :style="{ width: `${job.progress}%` }"
                  />
                </div>
                <span class="text-xs text-neutral-600 dark:text-neutral-400">
                  {{ job.progress }}%
                </span>
              </div>
            </td>
            <td class="px-4 py-3 text-sm text-neutral-600 dark:text-neutral-400">
              {{ timeAgo(job.created_at) }}
            </td>
            <td class="px-4 py-3 text-right">
              <button
                @click="$emit('view-details', job)"
                class="text-sm text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
              >
                Details
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="jobs.length === 0" class="py-12 text-center text-sm text-neutral-500 dark:text-neutral-400">
      No jobs found
    </div>
  </div>
</template>

<script setup lang="ts">
import type { JobInfo, JobStatus } from '~/types'
import { timeAgo } from '~/utils/format'

interface Props {
  jobs: JobInfo[]
}

defineProps<Props>()

defineEmits<{
  'view-details': [job: JobInfo]
}>()

const getStatusVariant = (status: JobStatus) => {
  const variants: Record<JobStatus, 'default' | 'primary' | 'warning' | 'success' | 'error'> = {
    pending: 'default',
    processing: 'primary',
    completed: 'success',
    failed: 'error'
  }
  return variants[status]
}

const getProgressColor = (status: JobStatus) => {
  const colors = {
    pending: 'bg-neutral-400',
    processing: 'bg-brand-600 dark:bg-brand-500',
    completed: 'bg-success-600 dark:bg-success-500',
    failed: 'bg-error-600 dark:bg-error-500'
  }
  return colors[status]
}
</script>
