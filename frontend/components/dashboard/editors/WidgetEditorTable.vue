<template>
  <div class="h-full overflow-y-auto p-5 space-y-5">

    <!-- Columns -->
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Columns</h3>
        <button
          v-if="editMode"
          class="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
          @click="addColumn()"
        >
          <span class="text-base leading-none">+</span> Add Column
        </button>
      </div>

      <div class="space-y-2">
        <TableColumnCard
          v-for="(col, i) in localColumns"
          :key="i"
          :model-value="col"
          :edit-mode="editMode"
          :available-keys="availableKeys"
          @update:model-value="updateColumn(i, $event)"
          @remove="removeColumn(i)"
        />
        <p v-if="localColumns.length === 0" class="text-xs text-gray-400 text-center py-4">
          No columns defined. Add a column to get started.
        </p>
      </div>
    </div>

    <!-- Options -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Options</h3>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Enable pagination</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localPagination"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localPagination ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && (localPagination = !localPagination, emitUpdate())"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localPagination ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>
      <div v-if="localPagination" class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Rows per page</span>
        <select
          v-model.number="localRowsPerPage"
          :disabled="!editMode"
          class="rounded border border-gray-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
          @change="emitUpdate()"
        >
          <option :value="10">10</option>
          <option :value="25">25</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
        </select>
      </div>
    </div>

    <!-- Default Sort -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Default Sort</h3>
      <div class="flex gap-2">
        <select
          v-model="localDefaultSortKey"
          :disabled="!editMode"
          class="flex-1 rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
          @change="emitUpdate()"
        >
          <option value="">None</option>
          <option v-for="col in localColumns" :key="col.key" :value="col.key">
            {{ col.label || col.key }}
          </option>
        </select>
        <div v-if="localDefaultSortKey" class="flex rounded border border-gray-200 overflow-hidden">
          <button
            v-for="dir in (['asc', 'desc'] as const)"
            :key="dir"
            type="button"
            :disabled="!editMode"
            class="px-2.5 py-1 text-xs font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localDefaultSortDir ?? 'asc') === dir
              ? 'bg-indigo-600 text-white'
              : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="editMode && (localDefaultSortDir = dir, emitUpdate())"
          >
            {{ dir === 'asc' ? '↑ Asc' : '↓ Desc' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Data note -->
    <p class="text-[11px] text-gray-400 bg-gray-100 rounded-lg px-3 py-2">
      Row data is managed via SQL data sources or AI generation.
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { WidgetConfig, TableWidgetConfig, TableColumn } from '~/types/dashboard'
import TableColumnCard from './TableColumnCard.vue'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
}>()

function getTableConfig(): TableWidgetConfig {
  return props.modelValue.config as TableWidgetConfig
}

const availableKeys = computed(() => {
  const rows = getTableConfig().rows ?? []
  return rows.length ? Object.keys(rows[0]) : []
})

const localColumns = ref<TableColumn[]>(JSON.parse(JSON.stringify(getTableConfig().columns)))
const localPagination = ref(getTableConfig().pagination ?? false)
const localRowsPerPage = ref(getTableConfig().rowsPerPage ?? 25)
const localDefaultSortKey = ref(getTableConfig().defaultSortKey ?? '')
const localDefaultSortDir = ref<'asc' | 'desc'>(getTableConfig().defaultSortDir ?? 'asc')

function emitUpdate() {
  const cfg = getTableConfig()
  emit('update:modelValue', {
    type: 'table',
    config: {
      ...cfg,
      columns: localColumns.value,
      pagination: localPagination.value || undefined,
      rowsPerPage: localPagination.value ? localRowsPerPage.value : undefined,
      defaultSortKey: localDefaultSortKey.value || undefined,
      defaultSortDir: localDefaultSortKey.value ? localDefaultSortDir.value : undefined,
    },
  })
}

function updateColumn(i: number, col: TableColumn) {
  localColumns.value[i] = col
  emitUpdate()
}

function addColumn() {
  localColumns.value.push({ key: '', label: '' })
  emitUpdate()
}

function removeColumn(i: number) {
  localColumns.value.splice(i, 1)
  emitUpdate()
}
</script>
