<template>
  <UiDialog :open="open" @update:open="$emit('update:open', $event)" title="Job Details" size="lg">
    <div v-if="job" class="space-y-4">
      <!-- Status -->
      <div class="flex items-center justify-between rounded-lg bg-neutral-50 p-4 dark:bg-neutral-800">
        <span class="text-sm font-medium text-neutral-700 dark:text-neutral-300">Status</span>
        <UiBadge :variant="getStatusVariant(job.status)" dot>
          {{ job.status }}
        </UiBadge>
      </div>

      <!-- Progress -->
      <div>
        <div class="mb-2 flex items-center justify-between text-sm">
          <span class="font-medium text-neutral-700 dark:text-neutral-300">Progress</span>
          <span class="text-neutral-600 dark:text-neutral-400">{{ job.progress }}%</span>
        </div>
        <UiProgressBar :value="job.progress" :variant="job.status === 'completed' ? 'success' : 'default'" />
      </div>

      <!-- Details Grid -->
      <div class="grid gap-3">
        <div class="flex justify-between rounded-lg border border-neutral-200 p-3 dark:border-neutral-700">
          <span class="text-sm text-neutral-600 dark:text-neutral-400">Job ID</span>
          <span class="text-sm font-mono text-neutral-900 dark:text-neutral-100">{{ job.job_id }}</span>
        </div>

        <div class="flex justify-between rounded-lg border border-neutral-200 p-3 dark:border-neutral-700">
          <span class="text-sm text-neutral-600 dark:text-neutral-400">File</span>
          <span class="text-sm font-medium text-neutral-900 dark:text-neutral-100">{{ job.file_name }}</span>
        </div>

        <div class="flex justify-between rounded-lg border border-neutral-200 p-3 dark:border-neutral-700">
          <span class="text-sm text-neutral-600 dark:text-neutral-400">Namespace</span>
          <span class="text-sm text-neutral-900 dark:text-neutral-100">{{ job.namespace }}</span>
        </div>

        <div class="flex justify-between rounded-lg border border-neutral-200 p-3 dark:border-neutral-700">
          <span class="text-sm text-neutral-600 dark:text-neutral-400">Created</span>
          <span class="text-sm text-neutral-900 dark:text-neutral-100">{{ formatDate(job.created_at) }}</span>
        </div>

        <div v-if="job.started_at" class="flex justify-between rounded-lg border border-neutral-200 p-3 dark:border-neutral-700">
          <span class="text-sm text-neutral-600 dark:text-neutral-400">Started</span>
          <span class="text-sm text-neutral-900 dark:text-neutral-100">{{ formatDate(job.started_at) }}</span>
        </div>

        <div v-if="job.completed_at" class="flex justify-between rounded-lg border border-neutral-200 p-3 dark:border-neutral-700">
          <span class="text-sm text-neutral-600 dark:text-neutral-400">Completed</span>
          <span class="text-sm text-neutral-900 dark:text-neutral-100">{{ formatDate(job.completed_at) }}</span>
        </div>

        <div v-if="job.chunks_processed && job.chunks_total" class="flex justify-between rounded-lg border border-neutral-200 p-3 dark:border-neutral-700">
          <span class="text-sm text-neutral-600 dark:text-neutral-400">Chunks</span>
          <span class="text-sm text-neutral-900 dark:text-neutral-100">{{ job.chunks_processed }} / {{ job.chunks_total }}</span>
        </div>

        <!-- Result -->
        <div v-if="job.result" class="rounded-lg border border-success-200 bg-success-50 p-3 dark:border-success-800 dark:bg-success-900/10">
          <h4 class="mb-2 text-sm font-medium text-success-900 dark:text-success-100">Result</h4>
          <div class="space-y-1 text-sm text-success-800 dark:text-success-200">
            <p>Chunks created: {{ job.result.chunks_created }}</p>
            <p>Vectors upserted: {{ job.result.vectors_upserted }}</p>
          </div>
        </div>

        <!-- Error -->
        <div v-if="job.error" class="rounded-lg border border-error-200 bg-error-50 p-3 dark:border-error-800 dark:bg-error-900/10">
          <h4 class="mb-2 text-sm font-medium text-error-900 dark:text-error-100">Error</h4>
          <p class="text-sm text-error-800 dark:text-error-200">{{ job.error }}</p>
        </div>
      </div>
    </div>

    <template #footer>
      <UiButton @click="$emit('update:open', false)">
        Close
      </UiButton>
    </template>
  </UiDialog>
</template>

<script setup lang="ts">
import type { JobInfo, JobStatus } from '~/types'
import { formatDate } from '~/utils/format'

interface Props {
  open: boolean
  job?: JobInfo | null
}

defineProps<Props>()

defineEmits<{
  'update:open': [value: boolean]
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
</script>
