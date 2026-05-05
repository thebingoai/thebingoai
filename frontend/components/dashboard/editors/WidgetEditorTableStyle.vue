<template>
  <div class="h-full overflow-y-auto p-5 space-y-5 [&>*+*]:border-t [&>*+*]:border-gray-200 [&>*+*]:pt-5">

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
          <ColorPickerPopover
            :model-value="localColors[col.key] || undefined"
            :disabled="!editMode"
            @update:model-value="(c) => c === undefined ? resetColor(col.key) : onColorInput(col.key, c)"
          />
        </div>
      </div>
    </div>

    <!-- Table Colors -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Table Colors</h3>
      <div class="space-y-2">
        <div v-for="colorOpt in tableColorOptions" :key="colorOpt.key" class="flex items-center justify-between">
          <span class="text-xs text-gray-700">{{ colorOpt.label }}</span>
          <ColorPickerPopover
            :model-value="localTableColors[colorOpt.key] || undefined"
            :disabled="!editMode"
            @update:model-value="(c) => c === undefined ? resetTableColor(colorOpt.key) : onTableColorInput(colorOpt.key, c)"
          />
        </div>
      </div>
    </div>

    <!-- Border -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Border</h3>

      <div class="flex items-center justify-between">
        <span class="text-xs text-gray-700">Color</span>
        <ColorPickerPopover
          :model-value="localBorderColor || undefined"
          :disabled="!editMode"
          @update:model-value="(c) => { localBorderColor = c ?? ''; emitUpdate() }"
        />
      </div>

      <div class="space-y-1.5">
        <label class="text-xs text-gray-700">Style</label>
        <div class="flex rounded border border-gray-200 overflow-hidden">
          <button
            v-for="opt in borderStyleOptions"
            :key="opt.value"
            type="button"
            :disabled="!editMode"
            class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localBorderStyle ?? 'solid') === opt.value
              ? 'bg-indigo-600 text-white'
              : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="editMode && setBorderStyle(opt.value)"
          >{{ opt.label }}</button>
        </div>
      </div>

      <div class="flex items-center justify-between gap-2">
        <span class="text-xs text-gray-700">Width</span>
        <div class="flex items-center gap-2 flex-1 max-w-[140px]">
          <input
            v-model.number="localBorderWidth"
            type="range"
            min="0"
            max="5"
            :disabled="!editMode"
            class="flex-1 disabled:opacity-40"
            @input="emitUpdate()"
          />
          <span class="text-[11px] text-gray-500 tabular-nums w-6 text-right">{{ localBorderWidth }}px</span>
        </div>
      </div>

      <div class="flex items-center justify-between gap-2">
        <span class="text-xs text-gray-700">Radius</span>
        <div class="flex items-center gap-2 flex-1 max-w-[140px]">
          <input
            v-model.number="localBorderRadius"
            type="range"
            min="0"
            max="16"
            :disabled="!editMode"
            class="flex-1 disabled:opacity-40"
            @input="emitUpdate()"
          />
          <span class="text-[11px] text-gray-500 tabular-nums w-6 text-right">{{ localBorderRadius }}px</span>
        </div>
      </div>
    </div>

    <!-- Font -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Font</h3>

      <div class="flex items-center justify-between gap-2">
        <span class="text-xs text-gray-700">Family</span>
        <select
          v-model="localFontFamily"
          :disabled="!editMode"
          class="rounded border border-gray-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
          @change="emitUpdate()"
        >
          <option value="system">System</option>
          <option value="sans">Sans-serif</option>
          <option value="serif">Serif</option>
          <option value="mono">Monospace</option>
        </select>
      </div>

      <div class="space-y-1.5">
        <label class="text-xs text-gray-700">Size</label>
        <div class="flex rounded border border-gray-200 overflow-hidden">
          <button
            v-for="opt in fontSizeOptions"
            :key="opt.value"
            type="button"
            :disabled="!editMode"
            class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localFontSize ?? 'sm') === opt.value
              ? 'bg-indigo-600 text-white'
              : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="editMode && setFontSize(opt.value)"
          >{{ opt.label }}</button>
        </div>
      </div>

      <div class="flex items-center justify-between">
        <span class="text-xs text-gray-700">Color</span>
        <ColorPickerPopover
          :model-value="localFontColor || undefined"
          :disabled="!editMode"
          @update:model-value="(c) => { localFontColor = c ?? ''; emitUpdate() }"
        />
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { WidgetConfig, TableWidgetConfig } from '~/types/dashboard'
import ColorPickerPopover from './ColorPickerPopover.vue'

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

// Border + font local state
const localBorderColor = ref(tableConfig.value.borderColor ?? '')
const localBorderStyle = ref<'solid' | 'dashed' | 'dotted' | 'none'>(tableConfig.value.borderStyle ?? 'solid')
const localBorderWidth = ref(tableConfig.value.borderWidth ?? 0)
const localBorderRadius = ref(tableConfig.value.borderRadius ?? 0)
const localFontFamily = ref<'system' | 'sans' | 'serif' | 'mono'>(tableConfig.value.fontFamily ?? 'system')
const localFontSize = ref<'xs' | 'sm' | 'md' | 'lg'>(tableConfig.value.fontSize ?? 'sm')
const localFontColor = ref(tableConfig.value.fontColor ?? '')

const borderStyleOptions = [
  { value: 'solid' as const, label: 'Solid' },
  { value: 'dashed' as const, label: 'Dashed' },
  { value: 'dotted' as const, label: 'Dotted' },
  { value: 'none' as const, label: 'None' },
]

const fontSizeOptions = [
  { value: 'xs' as const, label: 'XS' },
  { value: 'sm' as const, label: 'S' },
  { value: 'md' as const, label: 'M' },
  { value: 'lg' as const, label: 'L' },
]

function setBorderStyle(v: 'solid' | 'dashed' | 'dotted' | 'none') {
  localBorderStyle.value = v
  emitUpdate()
}

function setFontSize(v: 'xs' | 'sm' | 'md' | 'lg') {
  localFontSize.value = v
  emitUpdate()
}


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
      borderColor: localBorderColor.value || undefined,
      borderStyle: localBorderStyle.value !== 'solid' ? localBorderStyle.value : undefined,
      borderWidth: localBorderWidth.value > 0 ? localBorderWidth.value : undefined,
      borderRadius: localBorderRadius.value > 0 ? localBorderRadius.value : undefined,
      fontFamily: localFontFamily.value !== 'system' ? localFontFamily.value : undefined,
      fontSize: localFontSize.value !== 'sm' ? localFontSize.value : undefined,
      fontColor: localFontColor.value || undefined,
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
