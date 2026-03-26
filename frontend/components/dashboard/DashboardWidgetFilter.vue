<template>
  <div class="flex h-full flex-wrap items-center gap-3 p-3">
    <div
      v-for="control in config.controls"
      :key="control.key"
      class="flex items-center gap-2"
    >
      <label class="text-xs font-medium text-gray-500 whitespace-nowrap">{{ control.label }}</label>

      <!-- Single-select dropdown -->
      <select
        v-if="control.type === 'dropdown' && !control.multiple"
        class="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-gray-400 focus:outline-none"
        :value="store.filterValues[control.key] ?? ''"
        @change="onDropdownChange(control.key, ($event.target as HTMLSelectElement).value)"
      >
        <option value="">All</option>
        <option
          v-for="opt in getOptions(control)"
          :key="opt"
          :value="opt"
        >{{ opt }}</option>
      </select>

      <!-- Multi-select dropdown -->
      <div
        v-else-if="control.type === 'dropdown' && control.multiple"
        :ref="el => { if (el) multiDropdownRefs.set(control.key, el as HTMLElement) }"
        class="relative"
      >
        <button
          class="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 hover:border-gray-300 focus:outline-none min-w-[100px]"
          @click="toggleMultiDropdown(control.key)"
        >
          <span v-if="getSelectedMulti(control.key).length === 0" class="text-gray-400">All</span>
          <span v-else>{{ getSelectedMulti(control.key).length }} selected</span>
          <ChevronDown class="h-3 w-3 text-gray-400 ml-auto" />
        </button>
        <div
          v-if="openMultiKey === control.key"
          class="absolute top-full left-0 z-50 mt-1 w-48 max-h-48 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg"
        >
          <label
            v-for="opt in getOptions(control)"
            :key="opt"
            class="flex items-center gap-2 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 cursor-pointer"
          >
            <input
              type="checkbox"
              :checked="getSelectedMulti(control.key).includes(opt)"
              class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-300"
              @change="toggleMultiOption(control.key, opt)"
            />
            {{ opt }}
          </label>
          <div v-if="getOptions(control).length === 0" class="px-3 py-2 text-xs text-gray-400">
            No options available
          </div>
        </div>
      </div>

      <!-- Search input -->
      <input
        v-else-if="control.type === 'search'"
        type="text"
        placeholder="Search..."
        class="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-gray-400 focus:outline-none w-36"
        :value="store.filterValues[control.key] ?? ''"
        @input="onSearchInput(control.key, ($event.target as HTMLInputElement).value)"
      />

      <!-- Date range -->
      <div
        v-else-if="control.type === 'date_range'"
        class="flex items-center gap-1.5"
      >
        <input
          type="date"
          class="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-gray-400 focus:outline-none"
          :value="(store.filterValues[control.key] as any)?.from ?? ''"
          @change="onDateChange(control.key, 'from', ($event.target as HTMLInputElement).value)"
        />
        <span class="text-xs text-gray-400">to</span>
        <input
          type="date"
          class="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-gray-400 focus:outline-none"
          :value="(store.filterValues[control.key] as any)?.to ?? ''"
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
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { SlidersHorizontal, ChevronDown } from 'lucide-vue-next'
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

// Multi-select dropdown open state
const openMultiKey = ref<string | null>(null)
const multiDropdownRefs = ref<Map<string, HTMLElement>>(new Map())

function getOptions(control: FilterControl): string[] {
  return dynamicOptions.value.get(control.key) ?? control.options ?? []
}

function getSelectedMulti(key: string): string[] {
  const val = store.filterValues[key]
  return Array.isArray(val) ? val : []
}

function onDropdownChange(key: string, value: string) {
  store.setFilterValue(key, value || null)
}

function toggleMultiDropdown(key: string) {
  openMultiKey.value = openMultiKey.value === key ? null : key
}

function toggleMultiOption(key: string, opt: string) {
  const current = getSelectedMulti(key)
  const next = current.includes(opt)
    ? current.filter(v => v !== opt)
    : [...current, opt]
  store.setFilterValue(key, next.length > 0 ? next : null)
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
  const current = (store.filterValues[key] as { from?: string; to?: string }) ?? {}
  const updated = { ...current, [side]: value || undefined }
  if (updated.from || updated.to) {
    store.setFilterValue(key, updated)
  } else {
    store.setFilterValue(key, null)
  }
}

function onClickOutside(e: MouseEvent) {
  if (!openMultiKey.value) return
  const container = multiDropdownRefs.value.get(openMultiKey.value)
  if (container && !container.contains(e.target as Node)) {
    openMultiKey.value = null
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
  document.addEventListener('click', onClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
  searchTimers.value.forEach(timer => clearTimeout(timer))
  searchTimers.value.clear()
})
</script>
