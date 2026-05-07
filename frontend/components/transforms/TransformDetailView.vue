<template>
  <div class="p-4 md:p-6">
    <!-- Back nav -->
    <button
      class="mb-4 flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 dark:text-neutral-400 dark:hover:text-neutral-100 transition-colors"
      @click="emit('back')"
    >
      <ArrowLeft class="h-4 w-4" />
      All Transforms
    </button>

    <!-- Loading -->
    <div v-if="loadingTransform" class="space-y-4">
      <UiSkeleton class="h-10 w-64 rounded-lg" />
      <UiSkeleton class="h-32 w-full rounded-lg" />
      <UiSkeleton class="h-48 w-full rounded-lg" />
    </div>

    <!-- Error -->
    <div
      v-else-if="transformError"
      class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400"
    >
      {{ transformError }}
    </div>

    <template v-else-if="transform">
      <!-- Header -->
      <div class="mb-6 flex items-start justify-between gap-4">
        <div>
          <div class="flex items-center gap-2 flex-wrap">
            <h1 class="text-2xl font-medium text-gray-900 dark:text-neutral-100">{{ transform.name }}</h1>
            <UiBadge :variant="statusVariant(transform.last_run_status)" size="sm" :dot="true">
              {{ statusLabel(transform.last_run_status) }}
            </UiBadge>
            <UiBadge v-if="!transform.enabled" variant="warning" size="sm">Disabled</UiBadge>
          </div>
          <p class="mt-1 text-sm text-gray-500 dark:text-neutral-400">
            Transform ID: <code class="font-mono text-xs">{{ transform.id }}</code>
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
        <h2 class="text-sm font-medium text-gray-700 dark:text-neutral-300 mb-3">Transform Details</h2>
        <dl class="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-3 text-sm">
          <div>
            <dt class="text-xs text-gray-500 dark:text-neutral-400">Materialization</dt>
            <dd class="mt-0.5 text-gray-900 dark:text-neutral-100 capitalize">{{ transform.materialization }}</dd>
          </div>
          <div v-if="transform.unique_key">
            <dt class="text-xs text-gray-500 dark:text-neutral-400">Unique Key</dt>
            <dd class="mt-0.5 text-gray-900 dark:text-neutral-100 font-mono text-xs">{{ transform.unique_key }}</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500 dark:text-neutral-400">Schedule</dt>
            <dd class="mt-0.5 text-gray-900 dark:text-neutral-100 font-mono text-xs">
              {{ transform.cron || 'Manual only' }}
            </dd>
          </div>
          <div v-if="transform.last_run_at">
            <dt class="text-xs text-gray-500 dark:text-neutral-400">Last Run</dt>
            <dd class="mt-0.5 text-gray-900 dark:text-neutral-100">{{ formatDate(transform.last_run_at) }}</dd>
          </div>
          <div v-if="transform.next_run_at">
            <dt class="text-xs text-gray-500 dark:text-neutral-400">Next Run</dt>
            <dd class="mt-0.5 text-gray-900 dark:text-neutral-100">{{ formatDate(transform.next_run_at) }}</dd>
          </div>
        </dl>

        <!-- SQL preview -->
        <div v-if="transform.sql" class="mt-4">
          <dt class="text-xs text-gray-500 dark:text-neutral-400 mb-1">SQL Preview</dt>
          <pre class="text-xs font-mono bg-gray-50 dark:bg-neutral-900 rounded-md px-3 py-2 text-gray-800 dark:text-neutral-200 overflow-x-auto whitespace-pre-wrap break-all">{{ transform.sql.slice(0, 200) }}{{ transform.sql.length > 200 ? '…' : '' }}</pre>
        </div>
      </UiCard>

      <!-- Run trigger feedback -->
      <div
        v-if="runFeedback"
        class="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-400"
      >
        {{ runFeedback }}
      </div>

      <!-- SQL Editor -->
      <UiCard class="mb-6 px-5 py-4">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-base font-medium text-gray-900 dark:text-neutral-100">SQL</h2>
          <UiButton size="sm" :loading="saving" :disabled="saving || sqlDraft === transform.sql" @click="handleSave">
            Save
          </UiButton>
        </div>
        <textarea
          v-model="sqlDraft"
          rows="12"
          spellcheck="false"
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:placeholder:text-neutral-500 dark:focus:ring-neutral-400 font-mono resize-y"
          placeholder="SELECT ..."
        />
        <p v-if="saveError" class="mt-1.5 text-sm text-red-600">{{ saveError }}</p>
      </UiCard>

      <!-- Last write (lineage) -->
      <div v-if="transform?.name">
        <LineageLastWritePanel :table="transform.name" />
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

        <SharedRunHistoryDrawer :runs="runs" :loading="loadingRuns" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ArrowLeft, Play } from 'lucide-vue-next'
import { useUserTransforms, type Transform, type TransformRun } from '~/composables/useUserTransforms'

const props = defineProps<{
  id: string
}>()

const emit = defineEmits<{ back: [] }>()

const { fetchTransform, triggerRun, fetchRuns, updateTransform } = useUserTransforms()

const transform = ref<Transform | null>(null)
const loadingTransform = ref(true)
const transformError = ref<string | null>(null)

const runs = ref<TransformRun[]>([])
const loadingRuns = ref(false)

const triggering = ref(false)
const runFeedback = ref<string | null>(null)

const sqlDraft = ref('')
const saving = ref(false)
const saveError = ref<string | null>(null)

watch(() => props.id, async (id) => {
  if (!id) return
  await Promise.all([loadTransform(), loadRuns()])
}, { immediate: true })

async function loadTransform() {
  loadingTransform.value = true
  transformError.value = null
  try {
    transform.value = await fetchTransform(props.id)
    sqlDraft.value = transform.value?.sql ?? ''
  } catch (e: unknown) {
    transformError.value = e instanceof Error ? e.message : 'Failed to load transform.'
  } finally {
    loadingTransform.value = false
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

async function handleSave() {
  saving.value = true
  saveError.value = null
  try {
    transform.value = await updateTransform(props.id, { sql: sqlDraft.value })
  } catch (e: unknown) {
    saveError.value = e instanceof Error ? e.message : 'Failed to save SQL.'
  } finally {
    saving.value = false
  }
}

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

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}
</script>
