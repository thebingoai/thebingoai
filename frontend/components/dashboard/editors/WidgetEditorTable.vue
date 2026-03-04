<template>
  <div class="flex h-full flex-col">
    <!-- Columns + options editor -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Left: columns editor -->
      <div class="w-96 flex-shrink-0 border-r border-gray-100 overflow-y-auto p-5 space-y-5">

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
            <div
              v-for="(col, i) in localColumns"
              :key="i"
              class="rounded-lg border border-gray-200 p-3 space-y-2 bg-gray-50"
            >
              <div class="flex gap-2">
                <div class="flex-1 space-y-1">
                  <label class="text-[10px] text-gray-400">Key</label>
                  <input
                    v-model="col.key"
                    type="text"
                    placeholder="column_key"
                    class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
                    :readonly="!editMode"
                    :class="!editMode ? 'cursor-default bg-gray-50' : ''"
                    @input="emitUpdate()"
                  />
                </div>
                <div class="flex-1 space-y-1">
                  <label class="text-[10px] text-gray-400">Label</label>
                  <input
                    v-model="col.label"
                    type="text"
                    placeholder="Display Label"
                    class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
                    :readonly="!editMode"
                    :class="!editMode ? 'cursor-default bg-gray-50' : ''"
                    @input="emitUpdate()"
                  />
                </div>
              </div>

              <div class="flex items-center gap-2">
                <div class="flex-1 space-y-1">
                  <label class="text-[10px] text-gray-400">Format</label>
                  <select
                    v-model="col.format"
                    :disabled="!editMode"
                    class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
                    @change="emitUpdate()"
                  >
                    <option value="">Default</option>
                    <option value="text">Text</option>
                    <option value="number">Number</option>
                    <option value="currency">Currency</option>
                    <option value="percent">Percent</option>
                    <option value="date">Date</option>
                  </select>
                </div>

                <label class="flex items-center gap-1.5 cursor-pointer select-none mt-4">
                  <input
                    type="checkbox"
                    :checked="col.sortable"
                    :disabled="!editMode"
                    class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-300"
                    @change="col.sortable = ($event.target as HTMLInputElement).checked; emitUpdate()"
                  />
                  <span class="text-xs text-gray-600">Sortable</span>
                </label>

                <button
                  v-if="editMode"
                  class="mt-4 flex h-5 w-5 items-center justify-center rounded text-gray-300 hover:bg-rose-50 hover:text-rose-500 transition-colors"
                  title="Remove column"
                  @click="removeColumn(i)"
                >
                  <X class="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            <p v-if="localColumns.length === 0" class="text-xs text-gray-400 text-center py-4">
              No columns defined. Add a column to get started.
            </p>
          </div>
        </div>

        <!-- Options -->
        <div class="space-y-3">
          <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Options</h3>
          <label class="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              :checked="localPagination"
              :disabled="!editMode"
              class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-300"
              @change="localPagination = ($event.target as HTMLInputElement).checked; emitUpdate()"
            />
            <span class="text-sm text-gray-700">Enable pagination</span>
          </label>
        </div>

        <!-- Data note -->
        <p class="text-[11px] text-gray-400 bg-gray-100 rounded-lg px-3 py-2">
          Row data is managed via SQL data sources or AI generation.
        </p>
      </div>

      <!-- Right: data preview -->
      <div class="flex-1 overflow-hidden flex flex-col">
        <div class="px-4 py-2 border-b border-gray-100 flex-shrink-0">
          <span class="text-[11px] font-medium text-gray-400 uppercase tracking-wide">
            Preview ({{ previewConfig.rows.length }} rows)
          </span>
        </div>
        <div class="flex-1 overflow-auto min-h-0">
          <DashboardWidgetTable :config="previewConfig" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { X } from 'lucide-vue-next'
import type { WidgetConfig, TableWidgetConfig, TableColumn } from '~/types/dashboard'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
}>()

const tableConfig = computed(() => props.modelValue.config as TableWidgetConfig)

const localColumns = ref<TableColumn[]>(
  JSON.parse(JSON.stringify(tableConfig.value.columns)),
)
const localPagination = ref(tableConfig.value.pagination ?? false)

const previewConfig = computed(() => tableConfig.value)

function emitUpdate() {
  emit('update:modelValue', {
    type: 'table',
    config: {
      columns: localColumns.value,
      rows: tableConfig.value.rows,
      pagination: localPagination.value || undefined,
    },
  })
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
