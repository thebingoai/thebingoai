<template>
  <div class="flex h-full flex-wrap items-center gap-3 p-3">
    <div
      v-for="control in config.controls"
      :key="control.key"
      class="flex items-center gap-2"
    >
      <label class="text-xs font-medium text-gray-500 whitespace-nowrap">{{ control.label }}</label>
      <select
        v-if="control.type === 'dropdown'"
        class="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-gray-400 focus:outline-none"
        @change="onDropdownChange(control.key, ($event.target as HTMLSelectElement).value)"
      >
        <option value="">All</option>
        <option
          v-for="opt in getOptions(control)"
          :key="opt"
          :value="opt"
        >{{ opt }}</option>
      </select>
      <input
        v-else-if="control.type === 'search'"
        type="text"
        placeholder="Search..."
        class="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-gray-400 focus:outline-none w-36"
        @input="onSearchInput(control.key, ($event.target as HTMLInputElement).value)"
      />
      <div
        v-else-if="control.type === 'date_range'"
        class="flex items-center gap-1.5"
      >
        <input
          type="date"
          class="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-gray-400 focus:outline-none"
          @change="onDateChange(control.key, 'from', ($event.target as HTMLInputElement).value)"
        />
        <span class="text-xs text-gray-400">to</span>
        <input
          type="date"
          class="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-gray-400 focus:outline-none"
          @change="onDateChange(control.key, 'to', ($event.target as HTMLInputElement).value)"
        />
      </div>
    </div>
    <div v-if="config.controls.length === 0" class="flex items-center gap-2 text-xs text-gray-400">
      <SlidersHorizontal class="h-3.5 w-3.5" />
      <span>No filters configured</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { SlidersHorizontal } from 'lucide-vue-next'
import type { FilterWidgetConfig, FilterControl } from '~/types/dashboard'
import { useApi } from '~/composables/useApi'
import { useDashboardStore } from '~/stores/dashboard'

const props = defineProps<{
  config: FilterWidgetConfig
}>()

const store = useDashboardStore()
const api = useApi()

// Map from control.key → dynamically loaded option values
const dynamicOptions = ref<Map<string, string[]>>(new Map())

// Search debounce timers
const searchTimers = ref<Map<string, ReturnType<typeof setTimeout>>>(new Map())

// Date range state: key → { from?: string; to?: string }
const dateState = ref<Map<string, { from?: string; to?: string }>>(new Map())

function getOptions(control: FilterControl): string[] {
  return dynamicOptions.value.get(control.key) ?? control.options ?? []
}

function onDropdownChange(key: string, value: string) {
  store.setFilterValue(key, value || null)
}

function onSearchInput(key: string, value: string) {
  const existing = searchTimers.value.get(key)
  if (existing) clearTimeout(existing)
  const timer = setTimeout(() => {
    store.setFilterValue(key, value || null)
  }, 300)
  searchTimers.value.set(key, timer)
}

function onDateChange(key: string, side: 'from' | 'to', value: string) {
  const current = dateState.value.get(key) ?? {}
  const updated = { ...current, [side]: value || undefined }
  dateState.value.set(key, updated)
  // Only emit when we have a complete range (or clear when both empty)
  if (updated.from || updated.to) {
    store.setFilterValue(key, updated)
  } else {
    store.setFilterValue(key, null)
  }
}

async function loadDynamicOptions() {
  for (const control of props.config.controls) {
    if (control.type !== 'dropdown' || !control.optionsSource) continue
    try {
      const { connectionId, sql } = control.optionsSource
      const response = await api.dashboards.refreshWidget({
        connection_id: connectionId,
        sql,
        mapping: { type: 'table', columnConfig: [{ column: 'option_value', label: 'Option' }] },
        limit: 100,
      }) as { config: { rows: Record<string, any>[] } }
      const options = response.config.rows
        .map((r: Record<string, any>) => r.option_value ?? Object.values(r)[0])
        .filter(Boolean)
        .map(String)
      dynamicOptions.value = new Map(dynamicOptions.value).set(control.key, options)
    } catch (err) {
      // Fall back to static options on error
    }
  }
}

onMounted(() => {
  loadDynamicOptions()
})
</script>
