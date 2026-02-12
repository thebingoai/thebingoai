<template>
  <div class="container mx-auto p-6">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
          Jobs
        </h1>
        <p class="mt-2 text-neutral-600 dark:text-neutral-400">
          Monitor upload and processing jobs
        </p>
      </div>
      <UiButton @click="() => refreshJobs()" :loading="pending">
        <component :is="RefreshCw" class="h-4 w-4" />
        Refresh
      </UiButton>
    </div>

    <!-- Filters -->
    <div class="mb-6 flex flex-wrap gap-4">
      <UiSelect
        v-model="selectedStatus"
        :options="statusOptions"
        placeholder="All statuses"
        class="w-40"
      />
      <UiSelect
        v-model="selectedNamespace"
        :options="namespaceOptions"
        placeholder="All namespaces"
        class="w-40"
      />
    </div>

    <!-- Jobs Table -->
    <div v-if="pending" class="space-y-3">
      <UiSkeleton v-for="i in 5" :key="i" height="60px" />
    </div>

    <div v-else-if="error" class="rounded-lg border border-error-200 bg-error-50 p-6 dark:border-error-800 dark:bg-error-900/10">
      <p class="text-error-700 dark:text-error-400">
        Failed to load jobs: {{ error }}
      </p>
    </div>

    <JobsTable
      v-else
      :jobs="filteredJobs"
      @view-details="viewJobDetails"
    />

    <!-- Job Detail Modal -->
    <JobDetailModal
      v-model:open="showDetailModal"
      :job="selectedJob"
    />
  </div>
</template>

<script setup lang="ts">
import { RefreshCw } from 'lucide-vue-next'
import type { JobInfo } from '~/types'
import { useIntervalFn } from '@vueuse/core'

const selectedStatus = ref<string>('')
const selectedNamespace = ref<string>('')
const selectedJob = ref<JobInfo | null>(null)
const showDetailModal = ref(false)

const { namespaceNames } = useNamespaces()

// Fetch jobs
const { data: jobsData, pending, error, refresh: refreshJobs } = useJobs()

const jobs = computed(() => jobsData.value?.jobs || [])

// Filter jobs
const filteredJobs = computed(() => {
  let filtered = jobs.value

  if (selectedStatus.value) {
    filtered = filtered.filter(j => j.status === selectedStatus.value)
  }

  if (selectedNamespace.value) {
    filtered = filtered.filter(j => j.namespace === selectedNamespace.value)
  }

  return filtered
})

// Filter options
const statusOptions = [
  { label: 'All statuses', value: '' },
  { label: 'Pending', value: 'pending' },
  { label: 'Processing', value: 'processing' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' }
]

const namespaceOptions = computed(() => [
  { label: 'All namespaces', value: '' },
  ...namespaceNames.value.map(ns => ({ label: ns, value: ns }))
])

const viewJobDetails = (job: JobInfo) => {
  selectedJob.value = job
  showDetailModal.value = true
}

// Auto-refresh for active jobs
const hasActiveJobs = computed(() =>
  jobs.value.some(j => j.status === 'pending' || j.status === 'processing')
)

useIntervalFn(() => {
  if (hasActiveJobs.value) {
    refreshJobs()
  }
}, 5000) // Refresh every 5 seconds if there are active jobs
</script>
