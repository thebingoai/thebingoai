<template>
  <div class="p-4 md:p-6">
    <!-- Back nav -->
    <button
      class="mb-4 flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 dark:text-neutral-400 dark:hover:text-neutral-100 transition-colors"
      @click="emit('back')"
    >
      <ArrowLeft class="h-4 w-4" />
      All Pipelines
    </button>

    <!-- Loading -->
    <div v-if="loadingPipeline" class="space-y-4">
      <UiSkeleton class="h-10 w-64 rounded-lg" />
      <UiSkeleton class="h-32 w-full rounded-lg" />
      <UiSkeleton class="h-48 w-full rounded-lg" />
    </div>

    <!-- Error -->
    <div
      v-else-if="pipelineError"
      class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400"
    >
      {{ pipelineError }}
    </div>

    <template v-else-if="pipeline">
      <!-- Header -->
      <div class="mb-6 flex items-start justify-between gap-4">
        <div>
          <div class="flex items-center gap-2 flex-wrap">
            <h1 class="text-2xl font-medium text-gray-900 dark:text-neutral-100">{{ pipeline.name }}</h1>
            <UiBadge :variant="statusVariant(pipeline.last_run_status)" size="sm" :dot="true">
              {{ statusLabel(pipeline.last_run_status) }}
            </UiBadge>
            <UiBadge v-if="!pipeline.enabled" variant="warning" size="sm">Disabled</UiBadge>
          </div>
          <p class="mt-1 text-sm text-gray-500 dark:text-neutral-400">
            Pipeline ID: <code class="font-mono text-xs">{{ pipeline.id }}</code>
          </p>
        </div>

        <UiButton
          :loading="triggering"
          :disabled="triggering"
          @click="handleRun"
        >
          <Play class="h-4 w-4" />
          Run Now
        </UiButton>
      </div>

      <!-- Info card -->
      <UiCard class="mb-6 px-5 py-4">
        <h2 class="text-sm font-medium text-gray-700 dark:text-neutral-300 mb-3">Pipeline Details</h2>
        <dl class="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-3 text-sm">
          <div>
            <dt class="text-xs text-gray-500 dark:text-neutral-400">Source Connection</dt>
            <dd class="mt-0.5 text-gray-900 dark:text-neutral-100 flex items-center gap-1">
              <Database class="h-3.5 w-3.5 text-gray-400" />
              Connection #{{ pipeline.source_connection_id }}
            </dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500 dark:text-neutral-400">Target Table</dt>
            <dd class="mt-0.5 text-gray-900 dark:text-neutral-100 font-mono text-xs">{{ pipeline.target_table }}</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500 dark:text-neutral-400">Mode</dt>
            <dd class="mt-0.5 text-gray-900 dark:text-neutral-100 capitalize">{{ pipeline.mode }}</dd>
          </div>
          <div v-if="pipeline.incremental_key">
            <dt class="text-xs text-gray-500 dark:text-neutral-400">Incremental Key</dt>
            <dd class="mt-0.5 text-gray-900 dark:text-neutral-100 font-mono text-xs">{{ pipeline.incremental_key }}</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500 dark:text-neutral-400">Schedule</dt>
            <dd class="mt-0.5 text-gray-900 dark:text-neutral-100 font-mono text-xs">
              {{ pipeline.cron || 'Manual only' }}
            </dd>
          </div>
          <div v-if="pipeline.last_run_at">
            <dt class="text-xs text-gray-500 dark:text-neutral-400">Last Run</dt>
            <dd class="mt-0.5 text-gray-900 dark:text-neutral-100">{{ formatDate(pipeline.last_run_at) }}</dd>
          </div>
          <div v-if="pipeline.next_run_at">
            <dt class="text-xs text-gray-500 dark:text-neutral-400">Next Run</dt>
            <dd class="mt-0.5 text-gray-900 dark:text-neutral-100">{{ formatDate(pipeline.next_run_at) }}</dd>
          </div>
        </dl>
      </UiCard>

      <!-- Last write (lineage) -->
      <div v-if="pipeline?.target_table" class="mb-4">
        <LineageLastWritePanel :table="pipeline.target_table" />
      </div>

      <!-- Run trigger feedback -->
      <div
        v-if="runFeedback"
        class="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-400"
      >
        {{ runFeedback }}
      </div>

      <!-- Run history -->
      <div>
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-base font-medium text-gray-900 dark:text-neutral-100">Run History</h2>
          <button
            class="text-xs text-gray-500 hover:text-gray-800 dark:text-neutral-400 dark:hover:text-neutral-100"
            @click="loadRuns"
          >
            Refresh
          </button>
        </div>

        <div v-if="loadingRuns" class="space-y-2">
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
              <div v-if="run.rows_written !== null">
                {{ run.rows_written.toLocaleString() }} rows
              </div>
              <div v-if="run.finished_at && run.started_at">
                {{ formatDuration(run.started_at, run.finished_at) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ArrowLeft, Database, Play } from 'lucide-vue-next'
import { useUserPipelines, type Pipeline, type PipelineRun } from '~/composables/useUserPipelines'

const props = defineProps<{
  id: string
}>()

const emit = defineEmits<{ back: [] }>()

const { pipelines, fetchPipelines, triggerRun, fetchRuns } = useUserPipelines()

const pipeline = ref<Pipeline | null>(null)
const loadingPipeline = ref(true)
const pipelineError = ref<string | null>(null)

const runs = ref<PipelineRun[]>([])
const loadingRuns = ref(false)

const triggering = ref(false)
const runFeedback = ref<string | null>(null)

watch(() => props.id, async (id) => {
  if (!id) return
  await Promise.all([loadPipeline(), loadRuns()])
}, { immediate: true })

async function loadPipeline() {
  loadingPipeline.value = true
  pipelineError.value = null
  try {
    await fetchPipelines()
    pipeline.value = pipelines.value.find(p => p.id === props.id) ?? null
    if (!pipeline.value) {
      pipelineError.value = 'Pipeline not found.'
    }
  } catch (e: unknown) {
    pipelineError.value = e instanceof Error ? e.message : 'Failed to load pipeline.'
  } finally {
    loadingPipeline.value = false
  }
}

async function loadRuns() {
  loadingRuns.value = true
  try {
    runs.value = await fetchRuns(props.id)
  } catch {
    // non-fatal
  } finally {
    loadingRuns.value = false
  }
}

async function handleRun() {
  triggering.value = true
  runFeedback.value = null
  try {
    const result = await triggerRun(props.id)
    runFeedback.value = `Run triggered successfully (ID: ${result.run_id}).`
    await loadRuns()
  } catch (e: unknown) {
    runFeedback.value = `Failed to trigger run: ${e instanceof Error ? e.message : String(e)}`
  } finally {
    triggering.value = false
  }
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

function runStatusVariant(status: PipelineRun['status']): 'success' | 'error' | 'info' {
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
