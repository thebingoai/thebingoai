<template>
  <PipelineDetailView v-if="detailId" :id="detailId" @back="closeDetail" />

  <div v-else class="p-4 md:p-6">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-medium text-gray-900 dark:text-neutral-100">Pipelines</h1>
        <p class="mt-1 text-sm text-gray-500 dark:text-neutral-400">
          Manage scheduled data sync pipelines from your connections.
        </p>
      </div>
      <UiButton @click="showCreateModal = true">
        <Plus class="h-4 w-4" />
        New Pipeline
      </UiButton>
    </div>

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
      v-else-if="pipelines.length === 0"
      title="No pipelines yet"
      description="Create a pipeline to schedule automated data syncs from your connections."
      :icon="Workflow"
    >
      <template #action>
        <UiButton @click="showCreateModal = true">
          Create Your First Pipeline
        </UiButton>
      </template>
    </UiEmptyState>

    <!-- Pipeline list -->
    <div v-else class="space-y-3">
      <UiCard
        v-for="pipeline in pipelines"
        :key="pipeline.id"
        class="px-5 py-4 cursor-pointer hover:shadow-lg transition-shadow"
        @click="openDetail(pipeline.id)"
      >
        <div class="flex items-start justify-between gap-4">
          <!-- Left: name + meta -->
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-sm font-medium text-gray-900 dark:text-neutral-100 truncate">
                {{ pipeline.name }}
              </span>
              <UiBadge :variant="statusVariant(pipeline.last_run_status)" size="sm" :dot="true">
                {{ statusLabel(pipeline.last_run_status) }}
              </UiBadge>
              <UiBadge v-if="!pipeline.enabled" variant="warning" size="sm">Disabled</UiBadge>
            </div>

            <div class="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-neutral-400">
              <span class="flex items-center gap-1">
                <Database class="h-3 w-3" />
                Connection #{{ pipeline.source_connection_id }}
              </span>
              <span class="flex items-center gap-1">
                <Table2 class="h-3 w-3" />
                {{ pipeline.target_table }}
              </span>
              <span v-if="pipeline.cron" class="flex items-center gap-1">
                <Clock class="h-3 w-3" />
                {{ pipeline.cron }}
              </span>
              <span v-else class="flex items-center gap-1 italic">
                <Clock class="h-3 w-3" />
                Manual only
              </span>
            </div>

            <div v-if="pipeline.last_run_at" class="mt-1 text-xs text-gray-400 dark:text-neutral-500">
              Last run {{ formatRelative(pipeline.last_run_at) }}
              <template v-if="pipeline.next_run_at">
                · Next {{ formatRelative(pipeline.next_run_at) }}
              </template>
            </div>
          </div>

          <!-- Right: run button -->
          <div class="shrink-0 flex items-center gap-2">
            <UiButton
              size="sm"
              variant="outline"
              :loading="runningPipelines.has(pipeline.id)"
              @click.stop="handleRun(pipeline.id)"
              :disabled="runningPipelines.has(pipeline.id)"
            >
              <Play class="h-3.5 w-3.5" />
              Run
            </UiButton>
          </div>
        </div>
      </UiCard>
    </div>

    <!-- Create modal -->
    <PipelinesPipelineEditModal
      v-model:open="showCreateModal"
      @created="handleCreated"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Plus, Database, Clock, Play, Table2, Workflow } from 'lucide-vue-next'
import { useUserPipelines, type Pipeline } from '~/composables/useUserPipelines'

const route = useRoute()
const router = useRouter()

const detailId = computed(() => (route.query.id as string) || '')

function openDetail(id: string) {
  router.push({ query: { ...route.query, id } })
}

function closeDetail() {
  const next = { ...route.query }
  delete next.id
  router.replace({ query: next })
}

const { pipelines, loading, error, fetchPipelines, triggerRun } = useUserPipelines()
const showCreateModal = ref(false)
const runningPipelines = ref<Set<string>>(new Set())

onMounted(() => fetchPipelines())

async function handleRun(pipelineId: string) {
  runningPipelines.value = new Set([...runningPipelines.value, pipelineId])
  try {
    await triggerRun(pipelineId)
    await fetchPipelines()
  } finally {
    const next = new Set(runningPipelines.value)
    next.delete(pipelineId)
    runningPipelines.value = next
  }
}

function handleCreated() {
  showCreateModal.value = false
  fetchPipelines()
}

function statusVariant(status: Pipeline['last_run_status']): 'success' | 'error' | 'info' | 'default' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'running') return 'info'
  return 'default'
}

function statusLabel(status: Pipeline['last_run_status']): string {
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
