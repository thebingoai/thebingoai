<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useLineage, type LastWrite } from '~/composables/useLineage'

const props = defineProps<{
  table: string
}>()

const { getLastWrite } = useLineage()
const data = ref<LastWrite | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function load() {
  if (!props.table) return
  loading.value = true
  error.value = null
  try {
    data.value = await getLastWrite(props.table)
  } catch (e: any) {
    error.value = e?.message || 'Failed to load last-write info'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.table, load)
</script>

<template>
  <div class="rounded-lg border border-gray-200 dark:border-neutral-800 bg-gray-50 dark:bg-neutral-900 px-4 py-3 text-sm">
    <div class="flex items-center justify-between mb-1">
      <div class="text-xs uppercase tracking-wide text-gray-500 dark:text-neutral-400">
        Last write
      </div>
      <NuxtLink :to="`/lineage?table=${encodeURIComponent(table)}`" class="text-xs text-blue-600 hover:underline">
        Lineage →
      </NuxtLink>
    </div>

    <div v-if="loading" class="text-gray-500 dark:text-neutral-400 text-xs">Loading…</div>
    <div v-else-if="error" class="text-red-600 text-xs">{{ error }}</div>
    <div v-else-if="!data" class="text-gray-500 dark:text-neutral-400 text-xs">
      No write yet for <span class="font-mono">{{ table }}</span>
    </div>
    <div v-else class="space-y-1">
      <div>
        <span class="text-gray-500 dark:text-neutral-400">Written by</span>
        <span class="ml-1 font-medium text-gray-900 dark:text-neutral-100">
          {{ data.writer === 'pipeline' ? 'Pipeline' : 'dbt model' }}
        </span>
      </div>
      <div>
        <span class="text-gray-500 dark:text-neutral-400">Status</span>
        <span
          class="ml-1 inline-block px-2 py-0.5 rounded text-xs"
          :class="{
            'bg-green-100 text-green-800': data.status === 'success',
            'bg-red-100 text-red-800': data.status === 'failed',
            'bg-yellow-100 text-yellow-800': data.status === 'running',
          }"
        >
          {{ data.status }}
        </span>
      </div>
      <div v-if="data.finished_at">
        <span class="text-gray-500 dark:text-neutral-400">Finished</span>
        <span class="ml-1 text-gray-900 dark:text-neutral-100">{{ data.finished_at }}</span>
      </div>
      <div v-if="data.rows_written != null">
        <span class="text-gray-500 dark:text-neutral-400">Rows</span>
        <span class="ml-1 text-gray-900 dark:text-neutral-100">{{ data.rows_written.toLocaleString() }}</span>
      </div>
    </div>
  </div>
</template>
