<template>
  <div class="border-b border-[var(--line)]">
    <!-- Header -->
    <button
      @click="chatStore.toggleInfoSection('datasets')"
      class="w-full flex items-center justify-between px-4 py-3 hover:bg-[var(--paper-2)] transition-colors"
    >
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] uppercase tracking-wider text-[var(--ink-2)] font-semibold">Datasets</span>
        <span v-if="datasets.length" class="text-[9px] bg-[var(--paper-3)] text-[var(--ink-2)] px-1.5 py-px rounded-full">
          {{ datasets.length }}
        </span>
      </div>
      <svg
        class="w-3 h-3 text-[var(--ink-3)] transition-transform duration-200"
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
        <svg class="w-5 h-5 mx-auto text-[var(--ink-3)] mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p class="text-[11px] text-[var(--ink-3)]">No datasets uploaded yet</p>
      </div>

      <!-- Dataset list -->
      <div v-else class="flex flex-col gap-1.5">
        <div
          v-for="ds in datasets"
          :key="ds.fileId ?? ds.name"
        >
          <!-- Compact card: ready state -->
          <div
            v-if="ds.step === 'ready'"
            class="flex items-center gap-2 rounded-lg bg-[var(--paper-2)] px-2.5 py-2"
          >
            <!-- Green check -->
            <div class="w-3.5 h-3.5 rounded-full bg-emerald-500 flex items-center justify-center shrink-0">
              <svg class="w-2 h-2" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-[11px] font-medium text-[var(--ink-1)] truncate">{{ ds.name }}</p>
              <p class="text-[10px] text-[var(--ink-3)]">
                {{ formatSize(ds.size) }}
                <template v-if="ds.rowCount"> · {{ ds.rowCount.toLocaleString() }} rows</template>
                <template v-if="ds.columnCount"> · {{ ds.columnCount }} columns</template>
              </p>
            </div>
            <button
              v-if="ds.fileId"
              @click="cancelDataset(ds.fileId)"
              class="shrink-0 p-0.5 text-[var(--ink-3)] hover:text-red-400 transition-colors"
              title="Remove dataset"
            >
              <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Timeline card: in-progress or failed -->
          <div
            v-else
            class="rounded-lg bg-[var(--paper-1)] border px-2.5 py-2"
            :class="ds.step === 'failed' ? 'border-red-200' : 'border-[var(--line)]'"
          >
            <!-- File header -->
            <div class="flex items-center gap-2 mb-2">
              <svg class="w-3.5 h-3.5 text-[var(--ink-2)] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span class="text-[11px] font-medium text-[var(--ink-1)] truncate min-w-0 flex-1">{{ ds.name }}</span>
              <span class="text-[9px] text-[var(--ink-3)] shrink-0">{{ formatSize(ds.size) }}</span>
              <button
                v-if="ds.fileId"
                @click="cancelDataset(ds.fileId)"
                class="shrink-0 p-0.5 text-[var(--ink-3)] hover:text-red-400 transition-colors"
                :title="ds.step === 'failed' ? 'Remove' : 'Cancel'"
              >
                <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <!-- Vertical timeline -->
            <div class="pl-1">
              <!-- Step 1: Uploaded -->
              <DatasetTimelineStep
                :status="stepStatus(ds, 'uploading')"
                label="Uploaded"
                active-label="Uploading..."
                :timestamp="ds.uploadedAt"
                :is-last="false"
                :next-status="stepStatus(ds, 'schema')"
              />
              <!-- Step 2: Schema -->
              <DatasetTimelineStep
                :status="stepStatus(ds, 'schema')"
                label="Schema built"
                active-label="Building schema..."
                :timestamp="ds.schemaBuiltAt"
                :is-last="false"
                :next-status="stepStatus(ds, 'profiling')"
              />
              <!-- Step 3: Profiling -->
              <DatasetTimelineStep
                :status="stepStatus(ds, 'profiling')"
                label="Data profiled"
                active-label="Profiling data..."
                :timestamp="ds.profilingStartedAt"
                :is-last="true"
                :error="ds.step === 'failed' && stepStatus(ds, 'profiling') === 'failed' ? ds.error : null"
              />
            </div>

            <!-- Retry button for failed profiling -->
            <button
              v-if="ds.step === 'failed' && ds.connectionId && stepStatus(ds, 'profiling') === 'failed'"
              @click="retryProfiling(ds.connectionId!)"
              class="mt-1.5 ml-6 text-[9px] text-[var(--ink-2)] bg-[var(--paper-2)] border border-[var(--line)] rounded px-2 py-0.5 hover:bg-[var(--paper-3)] transition-colors"
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

const chatStore = useChatStore()
const { datasets, retryProfiling, cancelDataset } = useDatasetStatus()

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
</script>
