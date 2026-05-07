<script setup lang="ts">
import { computed } from 'vue'
import type { LineageNode } from '~/composables/useLineage'

const props = defineProps<{
  node: LineageNode | null
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const meta = computed(() => props.node?.meta ?? {})

const writerLabel = computed(() => {
  const w = meta.value.writer
  if (w === 'pipeline') return 'Pipeline'
  if (w === 'dbt') return 'dbt model'
  if (w === 'external') return 'External (live source)'
  return null
})

const lastRunStatus = computed(() => meta.value.last_run_status as string | null)
</script>

<template>
  <div
    v-if="node"
    class="border-l border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 w-80 flex-shrink-0 overflow-y-auto"
  >
    <div class="p-4 border-b border-gray-200 dark:border-neutral-800 flex items-start justify-between">
      <div>
        <div class="text-xs uppercase tracking-wide text-gray-500 dark:text-neutral-400">
          {{ node.kind }}
        </div>
        <div class="text-base font-medium text-gray-900 dark:text-neutral-100 mt-1 break-all">
          {{ node.name }}
        </div>
      </div>
      <button
        class="text-gray-400 hover:text-gray-600 dark:hover:text-neutral-200 text-sm"
        @click="emit('close')"
      >
        ✕
      </button>
    </div>

    <div class="p-4 space-y-3 text-sm">
      <div v-if="writerLabel">
        <div class="text-xs text-gray-500 dark:text-neutral-400">Written by</div>
        <div class="text-gray-900 dark:text-neutral-100">{{ writerLabel }}</div>
      </div>

      <div v-if="meta.last_run_at">
        <div class="text-xs text-gray-500 dark:text-neutral-400">Last run</div>
        <div class="text-gray-900 dark:text-neutral-100">{{ meta.last_run_at }}</div>
      </div>

      <div v-if="lastRunStatus">
        <div class="text-xs text-gray-500 dark:text-neutral-400">Status</div>
        <div
          class="inline-block px-2 py-0.5 rounded text-xs"
          :class="{
            'bg-green-100 text-green-800': lastRunStatus === 'success',
            'bg-red-100 text-red-800': lastRunStatus === 'failed',
            'bg-yellow-100 text-yellow-800': lastRunStatus === 'running',
          }"
        >
          {{ lastRunStatus }}
        </div>
      </div>

      <div v-if="node.kind === 'widget' && meta.lineage_status === 'incomplete'">
        <div class="rounded bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800 p-2 text-xs text-yellow-800 dark:text-yellow-300">
          Lineage incomplete — SQL not parseable. An admin will review.
        </div>
      </div>

      <div v-if="meta.materialization">
        <div class="text-xs text-gray-500 dark:text-neutral-400">Materialization</div>
        <div class="text-gray-900 dark:text-neutral-100">{{ meta.materialization }}</div>
      </div>

      <div v-if="meta.dashboard_id">
        <NuxtLink :to="`/dashboard?id=${meta.dashboard_id}`" class="text-xs text-blue-600 hover:underline">
          Open dashboard →
        </NuxtLink>
      </div>

      <div v-if="meta.pipeline_id">
        <NuxtLink :to="{ path: '/settings', query: { tab: 'pipelines', id: meta.pipeline_id } }" class="text-xs text-blue-600 hover:underline">
          Open pipeline →
        </NuxtLink>
      </div>

      <div v-if="meta.model_id">
        <NuxtLink :to="{ path: '/settings', query: { tab: 'transforms', id: meta.model_id } }" class="text-xs text-blue-600 hover:underline">
          Open transform →
        </NuxtLink>
      </div>
    </div>
  </div>
</template>
