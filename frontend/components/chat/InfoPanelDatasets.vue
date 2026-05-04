<template>
  <div class="border-b border-gray-100 dark:border-neutral-800">
    <!-- Header -->
    <button
      @click="chatStore.toggleInfoSection('datasets')"
      class="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 dark:hover:bg-neutral-800 transition-colors"
    >
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] uppercase tracking-wider text-gray-400 font-semibold">Datasets</span>
        <span v-if="datasets.length" class="text-[9px] bg-gray-100 dark:bg-neutral-700 text-gray-500 dark:text-neutral-300 px-1.5 py-px rounded-full">
          {{ datasets.length }}
        </span>
      </div>
      <svg
        class="w-3 h-3 text-gray-300 transition-transform duration-200"
        :class="{ 'rotate-180': chatStore.infoPanelSections.datasets }"
        fill="none" viewBox="0 0 24 24" stroke="currentColor"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Content -->
    <div v-show="chatStore.infoPanelSections.datasets" class="px-4 pb-3">
      <!-- Empty state -->
      <div v-if="!datasets.length" class="text-center py-4">
        <svg class="w-5 h-5 mx-auto text-gray-200 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p class="text-[11px] text-gray-300">No datasets uploaded yet</p>
      </div>

      <!-- Dataset list -->
      <div v-else class="flex flex-col gap-1.5">
        <div
          v-for="ds in datasets"
          :key="ds.fileId ?? ds.name"
        >
          <!-- Collapsible dataset card: ready state -->
          <div
            v-if="ds.step === 'ready'"
            class="group rounded-lg border border-gray-200 dark:border-neutral-700 overflow-hidden"
          >
            <!-- Header row: name | rows · size | × | ▼ -->
            <div class="flex items-center gap-1.5 px-2.5 py-2 hover:bg-gray-50 dark:hover:bg-neutral-800 transition-colors cursor-pointer" @click="toggleDataset(ds.fileId ?? ds.name)">
              <div class="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
              <p class="text-[11px] font-medium text-gray-700 dark:text-neutral-200 truncate flex-1 min-w-0">{{ ds.name }}</p>
              <span class="text-[10px] text-gray-400 dark:text-neutral-500 shrink-0 whitespace-nowrap">
                <template v-if="rowCount(ds) != null">{{ rowCount(ds)!.toLocaleString() }} rows<template v-if="ds.size"> · </template></template>
                <template v-if="ds.size">{{ formatSize(ds.size) }}</template>
              </span>
              <svg
                class="w-3 h-3 text-gray-400 dark:text-neutral-500 flex-shrink-0 transition-transform duration-200"
                :class="{ 'rotate-180': isExpanded(ds.fileId ?? ds.name) }"
                fill="none" viewBox="0 0 24 24" stroke="currentColor"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </div>
            <!-- Expandable column list -->
            <div
              v-if="isExpanded(ds.fileId ?? ds.name) && ds.connectionId"
              class="border-t border-gray-100 dark:border-neutral-800 px-2.5 py-2"
            >
              <!-- Loading skeleton -->
              <div v-if="schemaFor(ds.connectionId).loading" class="space-y-1.5 py-1">
                <div v-for="n in 5" :key="n" class="h-3 bg-gray-100 dark:bg-neutral-700 rounded animate-pulse" />
              </div>
              <!-- Error -->
              <p v-else-if="schemaFor(ds.connectionId).error" class="text-[10px] text-red-400">{{ schemaFor(ds.connectionId).error }}</p>
              <!-- Column list -->
              <div v-else-if="columnsFor(ds.connectionId)" class="space-y-0.5">
                <div
                  v-for="col in columnsFor(ds.connectionId)"
                  :key="col.name"
                  class="flex items-center gap-1.5 py-0.5 px-1"
                >
                  <span class="text-[11px] text-gray-600 dark:text-neutral-300 truncate flex-1 min-w-0">{{ col.name }}</span>
                  <span class="text-[9px] text-violet-400 bg-gray-100 dark:bg-neutral-700 px-1 py-0.5 rounded font-mono shrink-0">{{ col.type }}</span>
                  <span v-if="col.nullable" class="text-[9px] text-gray-400 dark:text-neutral-500 shrink-0">?</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Timeline card: in-progress or failed -->
          <div
            v-else
            class="rounded-lg bg-white border px-2.5 py-2"
            :class="ds.step === 'failed' ? 'border-red-200' : 'border-gray-200'"
          >
            <!-- File header -->
            <div class="flex items-center gap-2 mb-2">
              <svg class="w-3.5 h-3.5 text-gray-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span class="text-[11px] font-medium text-gray-600 truncate min-w-0 flex-1">{{ ds.name }}</span>
              <span class="text-[9px] text-gray-300 shrink-0">{{ formatSize(ds.size) }}</span>
            </div>

            <!-- Vertical timeline -->
            <div class="pl-1">
              <!-- Step 1: Uploaded -->
              <DatasetTimelineStep
                :status="stepStatus(ds, 'uploading')"
                label="Uploaded"
                active-label="Uploading..."
                :timestamp="stepTimestampFor(ds, 'uploading')"
                :is-last="false"
                :next-status="stepStatus(ds, 'schema')"
              />
              <!-- Step 2: Schema -->
              <DatasetTimelineStep
                :status="stepStatus(ds, 'schema')"
                label="Schema built"
                active-label="Building schema..."
                :timestamp="stepTimestampFor(ds, 'schema')"
                :is-last="false"
                :next-status="stepStatus(ds, 'profiling')"
              />
              <!-- Step 3: Profiling -->
              <DatasetTimelineStep
                :status="stepStatus(ds, 'profiling')"
                label="Data profiled"
                active-label="Profiling data..."
                :timestamp="stepTimestampFor(ds, 'profiling')"
                :is-last="true"
                :error="ds.step === 'failed' && stepStatus(ds, 'profiling') === 'failed' ? ds.error : null"
              />
            </div>

            <!-- Retry button for failed profiling -->
            <button
              v-if="ds.step === 'failed' && ds.connectionId && stepStatus(ds, 'profiling') === 'failed'"
              @click="retryProfiling(ds.connectionId!)"
              class="mt-1.5 ml-6 text-[9px] text-gray-500 bg-gray-100 border border-gray-200 rounded px-2 py-0.5 hover:bg-gray-200 transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DatasetStatus } from '~/composables/useDatasetStatus'
import type { DatabaseSchema, SchemaColumn } from '~/types/connection'

const chatStore = useChatStore()
const { datasets, retryProfiling, cancelDataset } = useDatasetStatus()

const api = useApi()

const schemaCache = ref<Map<number, { schema: DatabaseSchema | null; loading: boolean; error: string | null }>>(new Map())

function schemaFor(connectionId: number) {
  return schemaCache.value.get(connectionId) ?? { schema: null, loading: false, error: null }
}

async function fetchSchema(connectionId: number) {
  if (schemaCache.value.has(connectionId)) return
  schemaCache.value.set(connectionId, { schema: null, loading: true, error: null })
  schemaCache.value = new Map(schemaCache.value)
  try {
    const result = await (api.connections as any).getSchema(String(connectionId)) as DatabaseSchema
    schemaCache.value.set(connectionId, { schema: result, loading: false, error: null })
  } catch (err: any) {
    schemaCache.value.set(connectionId, { schema: null, loading: false, error: err?.message || 'Failed to load schema' })
  }
  schemaCache.value = new Map(schemaCache.value)
}

watch(
  () => datasets.value
    .filter(ds => ds.step === 'ready' && ds.connectionId)
    .map(ds => ds.connectionId)
    .join(','),
  () => {
    for (const ds of datasets.value.filter(ds => ds.step === 'ready' && ds.connectionId)) {
      fetchSchema(ds.connectionId!)
    }
  },
  { immediate: true },
)

type StepName = 'uploading' | 'schema' | 'profiling'
type StepState = 'completed' | 'active' | 'pending' | 'failed'

const STEP_ORDER: StepName[] = ['uploading', 'schema', 'profiling']

function stepStatus(ds: DatasetStatus, stepName: StepName): StepState {
  const stepIdx = STEP_ORDER.indexOf(stepName)
  const currentIdx = STEP_ORDER.indexOf(ds.step as StepName)

  // If dataset is ready, all steps are completed
  if (ds.step === 'ready') return 'completed'

  // If dataset failed, determine which step failed and derive states
  if (ds.step === 'failed') {
    let failedIdx: number
    if (ds.error === 'Upload failed') failedIdx = 0
    else if (!ds.connectionId) failedIdx = 1
    else failedIdx = 2

    if (stepIdx < failedIdx) return 'completed'
    if (stepIdx === failedIdx) return 'failed'
    return 'pending'
  }

  if (stepIdx < currentIdx) return 'completed'
  if (stepIdx === currentIdx) return 'active'
  return 'pending'
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Live clock for active steps — ticks every second
const currentTime = ref(new Date().toISOString())
let clockInterval: ReturnType<typeof setInterval> | null = null
onMounted(() => { clockInterval = setInterval(() => { currentTime.value = new Date().toISOString() }, 1000) })
onUnmounted(() => { if (clockInterval) clearInterval(clockInterval) })

function stepTimestampFor(ds: DatasetStatus, step: StepName): string | null {
  const status = stepStatus(ds, step)
  if (status === 'active') return currentTime.value
  if (status === 'completed') {
    if (step === 'uploading') return ds.uploadedAt
    if (step === 'schema') return ds.schemaBuiltAt
    if (step === 'profiling') return ds.completedAt
  }
  return null
}

// --- Collapsible dataset cards ---

const expandedDatasets = ref(new Set<string>())

function toggleDataset(key: string) {
  const next = new Set(expandedDatasets.value)
  next.has(key) ? next.delete(key) : next.add(key)
  expandedDatasets.value = next
}

function isExpanded(key: string): boolean {
  return expandedDatasets.value.has(key)
}

// Auto-expand a dataset card when it first transitions to ready
watch(
  () => datasets.value.filter(ds => ds.step === 'ready').map(ds => ds.fileId ?? ds.name).join(','),
  (next, prev) => {
    const prevKeys = new Set((prev ?? '').split(',').filter(Boolean))
    for (const key of (next ?? '').split(',').filter(Boolean)) {
      if (!prevKeys.has(key)) {
        expandedDatasets.value = new Set([...expandedDatasets.value, key])
      }
    }
  },
)

// Extracts columns from the first table in the schema (CSV datasets have exactly one table)
function columnsFor(connectionId: number): SchemaColumn[] | null {
  const cached = schemaFor(connectionId)
  if (!cached.schema) return null
  for (const schemaData of Object.values(cached.schema.schemas)) {
    for (const tableData of Object.values(schemaData.tables)) {
      return tableData.columns
    }
  }
  return []
}

// Row count from schema cache (first table's row_count), falls back to ds.rowCount
function rowCount(ds: DatasetStatus): number | null {
  if (ds.rowCount != null) return ds.rowCount
  if (ds.connectionId) {
    const cached = schemaFor(ds.connectionId)
    if (cached.schema) {
      for (const schema of Object.values(cached.schema.schemas)) {
        for (const table of Object.values((schema as any).tables)) {
          const count = (table as any).row_count
          if (count != null) return count as number
        }
      }
    }
  }
  return null
}
</script>

