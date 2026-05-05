<template>
  <div class="h-full overflow-y-auto p-5 space-y-5">

    <!-- Title -->
    <div class="space-y-2">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Title</h3>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Show title</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localShowTitle"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localShowTitle ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggleShowTitle()"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localShowTitle ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>
      <div v-if="localShowTitle" class="space-y-1">
        <label class="text-xs text-gray-700">Title text</label>
        <input
          v-model="localTitle"
          type="text"
          placeholder="Table title…"
          :readonly="!editMode"
          class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
          :class="!editMode ? 'cursor-default bg-gray-50' : ''"
          @input="emitUpdate()"
        />
      </div>
    </div>

    <!-- Table Body -->
    <div class="space-y-1">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-3">Table Body</h3>

      <div v-for="opt in bodyOptions" :key="opt.key" class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">{{ opt.label }}</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localFlags[opt.key]"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localFlags[opt.key] ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggleFlag(opt.key)"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localFlags[opt.key] ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>
    </div>

    <!-- Data -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Data</h3>

      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Summary row</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localShowSummaryRow"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localShowSummaryRow ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggleShowSummaryRow()"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localShowSummaryRow ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <div class="space-y-1.5">
        <label class="text-xs text-gray-700">Missing data display</label>
        <div class="flex rounded border border-gray-200 overflow-hidden">
          <button
            v-for="opt in missingOptions"
            :key="opt.value"
            type="button"
            :disabled="!editMode"
            class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="localMissingData === opt.value
              ? 'bg-indigo-600 text-white'
              : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="editMode && setMissingData(opt.value)"
          >{{ opt.label }}</button>
        </div>
      </div>
    </div>

    <!-- Colors (bar & heatmap columns) -->
    <div v-if="colorColumns.length > 0" class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">
        Colors
        <span class="normal-case font-normal text-gray-400 ml-1">(bar &amp; heatmap)</span>
      </h3>
      <div class="space-y-2">
        <div
          v-for="col in colorColumns"
          :key="col.key"
          class="flex items-center justify-between"
        >
          <span class="text-xs text-gray-700">
            {{ col.label || col.key }}
            <span class="text-gray-400 text-[10px] ml-1">({{ col.displayType }})</span>
          </span>
          <div class="flex items-center gap-2">
            <span v-if="!localColors[col.key]" class="text-[10px] text-gray-400">Theme</span>
            <input
              type="color"
              :value="localColors[col.key] ?? '#6366f1'"
              :disabled="!editMode"
              class="h-6 w-10 rounded border border-gray-200 cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 p-0.5"
              @input="onColorInput(col.key, ($event.target as HTMLInputElement).value)"
            />
            <button
              v-if="localColors[col.key] && editMode"
              class="text-[10px] text-gray-400 hover:text-gray-600"
              title="Reset to theme default"
              @click="resetColor(col.key)"
            >✕</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Table Colors -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Table Colors</h3>
      <div class="space-y-2">
        <div v-for="colorOpt in tableColorOptions" :key="colorOpt.key" class="flex items-center justify-between">
          <span class="text-xs text-gray-700">{{ colorOpt.label }}</span>
          <div class="flex items-center gap-2">
            <span v-if="!localTableColors[colorOpt.key]" class="text-[10px] text-gray-400">Default</span>
            <input
              type="color"
              :value="localTableColors[colorOpt.key] || '#ffffff'"
              :disabled="!editMode"
              class="h-6 w-10 rounded border border-gray-200 cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 p-0.5"
              @input="onTableColorInput(colorOpt.key, ($event.target as HTMLInputElement).value)"
            />
            <button
              v-if="localTableColors[colorOpt.key] && editMode"
              class="text-[10px] text-gray-400 hover:text-gray-600"
              title="Reset to default"
              @click="resetTableColor(colorOpt.key)"
            >✕</button>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { WidgetConfig, TableWidgetConfig } from '~/types/dashboard'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
}>()

const tableConfig = computed(() => props.modelValue.config as TableWidgetConfig)

const localShowTitle = ref(!!tableConfig.value.showTitle)
const localTitle = ref(tableConfig.value.title ?? '')
const localFlags = ref({
  showHeader: tableConfig.value.showHeader !== false,
  showRowNumbers: !!tableConfig.value.showRowNumbers,
  stripedRows: !!tableConfig.value.stripedRows,
  wrapText: !!tableConfig.value.wrapText,
  horizontalScrolling: !!tableConfig.value.horizontalScrolling,
})
const localShowSummaryRow = ref(!!tableConfig.value.showSummaryRow)
const localMissingData = ref<'dash' | 'blank' | 'noData'>(tableConfig.value.missingDataDisplay ?? 'dash')
const localColors = ref<Record<string, string>>({ ...(tableConfig.value.columnColors ?? {}) })

type TableColorKey = 'headerBackground' | 'cellBorderColor' | 'oddRowColor' | 'evenRowColor'

const tableColorOptions: { key: TableColorKey; label: string }[] = [
  { key: 'headerBackground', label: 'Header background' },
  { key: 'cellBorderColor', label: 'Cell border color' },
  { key: 'oddRowColor', label: 'Odd row color' },
  { key: 'evenRowColor', label: 'Even row color' },
]

const localTableColors = ref<Partial<Record<TableColorKey, string>>>({
  headerBackground: tableConfig.value.headerBackground ?? '',
  cellBorderColor: tableConfig.value.cellBorderColor ?? '',
  oddRowColor: tableConfig.value.oddRowColor ?? '',
  evenRowColor: tableConfig.value.evenRowColor ?? '',
})


const bodyOptions = [
  { key: 'showHeader' as const, label: 'Show header' },
  { key: 'showRowNumbers' as const, label: 'Row numbers' },
  { key: 'stripedRows' as const, label: 'Striped rows' },
  { key: 'wrapText' as const, label: 'Wrap text' },
  { key: 'horizontalScrolling' as const, label: 'Horizontal scrolling' },
]

const missingOptions = [
  { value: 'dash' as const, label: '— dash' },
  { value: 'blank' as const, label: 'Blank' },
  { value: 'noData' as const, label: 'No data' },
]

const colorColumns = computed(() =>
  tableConfig.value.columns.filter(c => c.displayType === 'bar' || c.displayType === 'heatmap'),
)

function toggleFlag(key: keyof typeof localFlags.value) {
  localFlags.value[key] = !localFlags.value[key]
  emitUpdate()
}

function toggleShowTitle() {
  localShowTitle.value = !localShowTitle.value
  emitUpdate()
}

function toggleShowSummaryRow() {
  localShowSummaryRow.value = !localShowSummaryRow.value
  emitUpdate()
}

function setMissingData(val: 'dash' | 'blank' | 'noData') {
  localMissingData.value = val
  emitUpdate()
}

function emitUpdate() {
  emit('update:modelValue', {
    type: 'table',
    config: {
      ...tableConfig.value,
      title: localTitle.value || undefined,
      showTitle: localShowTitle.value || undefined,
      showHeader: localFlags.value.showHeader ? undefined : false,
      showRowNumbers: localFlags.value.showRowNumbers || undefined,
      stripedRows: localFlags.value.stripedRows || undefined,
      wrapText: localFlags.value.wrapText || undefined,
      horizontalScrolling: localFlags.value.horizontalScrolling || undefined,
      showSummaryRow: localShowSummaryRow.value || undefined,
      missingDataDisplay: localMissingData.value !== 'dash' ? localMissingData.value : undefined,
      columnColors: Object.keys(localColors.value).length ? localColors.value : undefined,
      headerBackground: localTableColors.value.headerBackground || undefined,
      cellBorderColor: localTableColors.value.cellBorderColor || undefined,
      oddRowColor: localTableColors.value.oddRowColor || undefined,
      evenRowColor: localTableColors.value.evenRowColor || undefined,
    },
  })
}

function onColorInput(key: string, color: string) {
  localColors.value = { ...localColors.value, [key]: color }
  emitUpdate()
}

function resetColor(key: string) {
  const colors = { ...localColors.value }
  delete colors[key]
  localColors.value = colors
  emitUpdate()
}

function onTableColorInput(key: TableColorKey, color: string) {
  localTableColors.value = { ...localTableColors.value, [key]: color }
  emitUpdate()
}

function resetTableColor(key: TableColorKey) {
  localTableColors.value = { ...localTableColors.value, [key]: '' }
  emitUpdate()
}
</script>
