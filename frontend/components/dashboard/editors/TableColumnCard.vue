<template>
  <div
    class="relative rounded-lg border border-gray-200 bg-gray-50 transition-shadow"
    :class="[
      dragging ? 'shadow-lg ring-2 ring-indigo-300' : '',
      expanded ? 'p-3 pl-7 space-y-2' : '',
    ]"
    :draggable="dragging"
    @dragstart="onDragStart"
    @dragend="onDragEnd"
  >
    <!-- Drag handle -->
    <button
      v-if="editMode"
      type="button"
      class="absolute left-1 flex h-5 w-5 items-center justify-center text-gray-300 hover:text-gray-500 cursor-grab active:cursor-grabbing"
      :class="expanded ? 'top-2' : 'top-1.5'"
      title="Drag to reorder"
      @mousedown="dragging = true"
      @mouseup="dragging = false"
      @mouseleave="dragging = false"
    >
      <GripVertical class="h-4 w-4" />
    </button>

    <!-- Collapsed header bar (always visible) -->
    <button
      v-if="!expanded"
      type="button"
      class="flex w-full items-center justify-between pl-7 pr-3 py-2 text-left hover:bg-gray-100 rounded-lg transition-colors"
      @click="expanded = true"
    >
      <div class="flex items-center gap-2 min-w-0">
        <ChevronRight class="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
        <span class="text-sm font-medium text-gray-700 truncate">
          {{ local.label || local.key || 'Untitled column' }}
        </span>
        <span
          class="text-[9px] px-1.5 py-0.5 rounded font-semibold tracking-wide flex-shrink-0"
          :class="effectiveRole === 'metric'
            ? 'bg-indigo-50 text-indigo-600'
            : 'bg-emerald-50 text-emerald-600'"
        >
          {{ effectiveRole === 'metric' ? 'MET' : 'DIM' }}
        </span>
        <span v-if="local.format" class="text-[10px] text-gray-400 uppercase tracking-wide flex-shrink-0">
          {{ local.format }}
        </span>
        <span v-if="effectiveRole === 'metric' && local.aggregation && local.aggregation !== 'none'" class="text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 flex-shrink-0">
          {{ aggLabel(local.aggregation) }}
        </span>
      </div>
      <button
        v-if="editMode"
        type="button"
        class="flex h-5 w-5 items-center justify-center rounded text-gray-300 hover:bg-rose-50 hover:text-rose-500 transition-colors flex-shrink-0"
        title="Remove column"
        @click.stop="emit('remove')"
      >
        <X class="h-3.5 w-3.5" />
      </button>
    </button>

    <!-- Expanded body -->
    <template v-if="expanded">
    <!-- Collapse button (top-right) -->
    <button
      type="button"
      class="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded text-gray-400 hover:bg-gray-200 hover:text-gray-600 transition-colors z-10"
      title="Collapse"
      @click="expanded = false"
    >
      <ChevronDown class="h-3.5 w-3.5" />
    </button>

    <!-- Key + Label -->
    <div class="flex gap-2">
      <div class="flex-1 space-y-1">
        <label class="text-[10px] text-gray-400">Key</label>
        <input
          v-model="local.key"
          type="text"
          :list="availableKeys?.length ? datalistId : undefined"
          placeholder="column_key"
          class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
          :readonly="!editMode"
          :class="!editMode ? 'cursor-default bg-gray-50' : ''"
          @change="emitUpdate()"
          @input="emitUpdate()"
        />
        <datalist v-if="availableKeys?.length" :id="datalistId">
          <option v-for="k in availableKeys" :key="k" :value="k" />
        </datalist>
      </div>
      <div class="flex-1 space-y-1">
        <label class="text-[10px] text-gray-400">Label</label>
        <input
          v-model="local.label"
          type="text"
          placeholder="Display Label"
          class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
          :readonly="!editMode"
          :class="!editMode ? 'cursor-default bg-gray-50' : ''"
          @input="emitUpdate()"
        />
      </div>
    </div>

    <!-- Role: Dimension / Metric -->
    <div class="space-y-1">
      <label class="text-[10px] text-gray-400">Role</label>
      <div class="flex rounded border border-gray-200 overflow-hidden">
        <button
          v-for="r in (['dimension', 'metric'] as const)"
          :key="r"
          type="button"
          :disabled="!editMode"
          class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="effectiveRole === r
            ? 'bg-indigo-600 text-white'
            : 'bg-white text-gray-500 hover:bg-gray-50'"
          @click="editMode && setRole(r)"
        >{{ r === 'dimension' ? 'Dimension' : 'Metric' }}</button>
      </div>
    </div>

    <!-- Format + Alignment + Toggles + Delete -->
    <div class="flex items-center gap-2 flex-wrap">
      <!-- Format -->
      <div class="space-y-1" style="min-width:80px;">
        <label class="text-[10px] text-gray-400">Format</label>
        <select
          v-model="local.format"
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
          <option value="duration">Duration</option>
        </select>
      </div>

      <!-- Alignment -->
      <div class="space-y-1">
        <label class="text-[10px] text-gray-400">Align</label>
        <div class="flex gap-0.5">
          <button
            v-for="a in (['left', 'center', 'right'] as const)"
            :key="a"
            type="button"
            :disabled="!editMode"
            class="flex h-6 w-6 items-center justify-center rounded border transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(local.align ?? 'left') === a
              ? 'border-indigo-400 bg-indigo-50 text-indigo-600'
              : 'border-gray-200 bg-white text-gray-400 hover:border-gray-300'"
            :title="a"
            @click="editMode && setAlign(a)"
          >
            <AlignLeft v-if="a === 'left'" class="h-3 w-3" />
            <AlignCenter v-else-if="a === 'center'" class="h-3 w-3" />
            <AlignRight v-else class="h-3 w-3" />
          </button>
        </div>
      </div>

      <!-- Numeric toggles: Round + Digits -->
      <template v-if="isNumeric">
        <div class="flex items-center gap-1.5 mt-4">
          <span class="text-xs text-gray-600">Round</span>
          <button
            type="button"
            role="switch"
            :aria-checked="!!local.roundValue"
            :disabled="!editMode"
            class="relative inline-flex h-4 w-7 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="local.roundValue ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && toggleRound()"
          >
            <span
              class="pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="local.roundValue ? 'translate-x-3 ml-0.5' : 'translate-x-0 ml-0.5'"
            />
          </button>
        </div>
        <div v-if="local.roundValue" class="flex items-center gap-1.5 mt-4">
          <span class="text-xs text-gray-600">Digits</span>
          <input
            v-model.number="local.decimalPlaces"
            type="number"
            min="0"
            max="10"
            class="w-10 rounded border border-gray-200 bg-white px-1.5 py-0.5 text-xs text-center text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
            :readonly="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50' : ''"
            @input="emitUpdate()"
          />
        </div>
      </template>

      <!-- Sortable -->
      <div class="flex items-center gap-1.5 mt-4">
        <span class="text-xs text-gray-600">Sort</span>
        <button
          type="button"
          role="switch"
          :aria-checked="!!local.sortable"
          :disabled="!editMode"
          class="relative inline-flex h-4 w-7 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="local.sortable ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && (local.sortable = !local.sortable, emitUpdate())"
        >
          <span
            class="pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="local.sortable ? 'translate-x-3 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <!-- Filterable -->
      <div class="flex items-center gap-1.5 mt-4">
        <span class="text-xs text-gray-600">Filter</span>
        <button
          type="button"
          role="switch"
          :aria-checked="!!local.filterable"
          :disabled="!editMode"
          class="relative inline-flex h-4 w-7 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="local.filterable ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && (local.filterable = !local.filterable, emitUpdate())"
        >
          <span
            class="pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="local.filterable ? 'translate-x-3 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <!-- Delete -->
      <button
        v-if="editMode"
        class="mt-4 flex h-5 w-5 items-center justify-center rounded text-gray-300 hover:bg-rose-50 hover:text-rose-500 transition-colors ml-auto"
        title="Remove column"
        @click="emit('remove')"
      >
        <X class="h-3.5 w-3.5" />
      </button>
    </div>

    <!-- Metric-only controls -->
    <template v-if="effectiveRole === 'metric'">
      <!-- Aggregation (always visible for metrics; options vary by format) -->
      <div class="space-y-1">
        <label class="text-[10px] text-gray-400">Aggregation</label>
        <select
          v-model="local.aggregation"
          :disabled="!editMode"
          class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
          @change="emitUpdate()"
        >
          <option v-for="opt in aggregationOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>

      <!-- Numeric-only metric extras -->
      <template v-if="isNumeric">
        <!-- Display type -->
        <div class="space-y-1.5">
          <label class="text-[10px] text-gray-400">Display Type</label>
          <div class="flex rounded border border-gray-200 overflow-hidden">
            <button
              v-for="dt in (['number', 'bar', 'heatmap'] as const)"
              :key="dt"
              type="button"
              :disabled="!editMode"
              class="flex-1 py-1 text-[10px] font-medium capitalize transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="(local.displayType ?? 'number') === dt
                ? 'bg-indigo-600 text-white'
                : 'bg-white text-gray-500 hover:bg-gray-50'"
              @click="editMode && setDisplayType(dt)"
            >{{ dt }}</button>
          </div>
        </div>

        <!-- Show value toggle (bar only) -->
        <div v-if="(local.displayType ?? 'number') === 'bar'" class="flex items-center justify-between py-0.5">
          <span class="text-xs text-gray-700">Show value</span>
          <button
            type="button"
            role="switch"
            :aria-checked="local.showBarValue !== false"
            :disabled="!editMode"
            class="relative inline-flex h-4 w-7 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="local.showBarValue !== false ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && (local.showBarValue = !local.showBarValue, emitUpdate())"
          >
            <span
              class="pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="local.showBarValue !== false ? 'translate-x-3 ml-0.5' : 'translate-x-0 ml-0.5'"
            />
          </button>
        </div>

        <!-- Compact numbers -->
        <div class="flex items-center justify-between py-0.5">
          <span class="text-xs text-gray-700">Compact numbers</span>
          <button
            type="button"
            role="switch"
            :aria-checked="!!local.compactNumbers"
            :disabled="!editMode"
            class="relative inline-flex h-4 w-7 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="local.compactNumbers ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && (local.compactNumbers = !local.compactNumbers, emitUpdate())"
          >
            <span
              class="pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="local.compactNumbers ? 'translate-x-3 ml-0.5' : 'translate-x-0 ml-0.5'"
            />
          </button>
        </div>

        <!-- Comparison -->
        <div class="space-y-1">
          <label class="text-[10px] text-gray-400">Comparison</label>
          <select
            v-model="local.comparisonCalc"
            :disabled="!editMode"
            class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
            @change="emitUpdate()"
          >
            <option value="none">None</option>
            <option value="percentOfTotal">% of Total</option>
            <option value="diffFromTotal">Diff from Total</option>
            <option value="percentDiffFromTotal">% Diff from Total</option>
            <option value="percentOfMax">% of Max</option>
            <option value="diffFromMax">Diff from Max</option>
            <option value="percentDiffFromMax">% Diff from Max</option>
          </select>
        </div>

        <!-- Running Calc -->
        <div class="space-y-1">
          <label class="text-[10px] text-gray-400">Running Calc</label>
          <select
            v-model="local.runningCalc"
            :disabled="!editMode"
            class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
            @change="emitUpdate()"
          >
            <option value="none">None</option>
            <option value="runningSum">Running Sum</option>
            <option value="runningMin">Running Min</option>
            <option value="runningMax">Running Max</option>
            <option value="runningCount">Running Count</option>
            <option value="runningAverage">Running Average</option>
            <option value="runningDelta">Running Delta</option>
            <option value="runningPercentageDelta">Running % Delta</option>
          </select>
        </div>
      </template>
    </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed, ref } from 'vue'
import { X, AlignLeft, AlignCenter, AlignRight, GripVertical, ChevronRight, ChevronDown } from 'lucide-vue-next'
import type { TableColumn } from '~/types/dashboard'

const AGG_LABELS: Record<string, string> = {
  sum: 'Sum',
  average: 'Avg',
  count: 'Count',
  countDistinct: 'Count Distinct',
  min: 'Min',
  max: 'Max',
  median: 'Median',
  stdDev: 'Std Dev',
  variance: 'Variance',
}

function aggLabel(v?: string): string {
  return AGG_LABELS[v ?? ''] ?? v ?? ''
}

const props = defineProps<{
  modelValue: TableColumn
  editMode: boolean
  availableKeys?: string[]
  index?: number
}>()

const datalistId = `col-keys-${Math.random().toString(36).slice(2)}`
const dragging = ref(false)
// New (empty-key) columns default to expanded for easier first-time editing
const expanded = ref(!props.modelValue.key)

const emit = defineEmits<{
  'update:modelValue': [value: TableColumn]
  remove: []
  dragstart: [index: number]
  dragend: []
}>()

const NUMERIC_FORMATS = new Set(['number', 'currency', 'percent', 'duration'])
const isNumeric = computed(() => NUMERIC_FORMATS.has(local.format ?? ''))

const effectiveRole = computed<'dimension' | 'metric'>(
  () => local.role ?? (isNumeric.value ? 'metric' : 'dimension'),
)

const NUMERIC_AGG_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'sum', label: 'Sum' },
  { value: 'average', label: 'Average' },
  { value: 'count', label: 'Count' },
  { value: 'countDistinct', label: 'Count Distinct' },
  { value: 'min', label: 'Min' },
  { value: 'max', label: 'Max' },
  { value: 'median', label: 'Median' },
  { value: 'stdDev', label: 'Std Deviation' },
  { value: 'variance', label: 'Variance' },
]
const NON_NUMERIC_AGG_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'count', label: 'Count' },
  { value: 'countDistinct', label: 'Count Distinct' },
]
const aggregationOptions = computed(() =>
  isNumeric.value ? NUMERIC_AGG_OPTIONS : NON_NUMERIC_AGG_OPTIONS,
)

function setRole(r: 'dimension' | 'metric') {
  local.role = r
  // If switching to a non-numeric metric and aggregation was numeric-only, reset.
  if (r === 'metric' && !isNumeric.value && local.aggregation
    && !['none', 'count', 'countDistinct'].includes(local.aggregation)) {
    local.aggregation = 'none'
  }
  emitUpdate()
}

const local = reactive<TableColumn>({ ...props.modelValue })

function onDragStart(e: DragEvent) {
  if (!dragging.value || props.index === undefined) {
    e.preventDefault()
    return
  }
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
  emit('dragstart', props.index)
}

function onDragEnd() {
  dragging.value = false
  emit('dragend')
}

function emitUpdate() {
  emit('update:modelValue', { ...local })
}

function setAlign(a: 'left' | 'center' | 'right') {
  local.align = a
  emitUpdate()
}

function setDisplayType(dt: 'number' | 'bar' | 'heatmap') {
  local.displayType = dt
  emitUpdate()
}

function toggleRound() {
  local.roundValue = !local.roundValue
  if (local.roundValue) local.decimalPlaces = local.decimalPlaces ?? 2
  emitUpdate()
}
</script>
