<template>
  <div class="rounded-lg border border-gray-200 p-3 space-y-2 bg-gray-50">
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

    <!-- Display type (numeric columns only) -->
    <template v-if="isNumeric">
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

      <!-- Metrics calculations -->
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

      <div class="space-y-1">
        <label class="text-[10px] text-gray-400">Aggregation</label>
        <select
          v-model="local.aggregation"
          :disabled="!editMode"
          class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
          @change="emitUpdate()"
        >
          <option value="sum">Sum</option>
          <option value="average">Average</option>
          <option value="count">Count</option>
          <option value="countDistinct">Count Distinct</option>
          <option value="min">Min</option>
          <option value="max">Max</option>
          <option value="median">Median</option>
          <option value="stdDev">Std Deviation</option>
          <option value="variance">Variance</option>
        </select>
      </div>

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
  </div>
</template>

<script setup lang="ts">
import { reactive, watch, computed } from 'vue'
import { X, AlignLeft, AlignCenter, AlignRight } from 'lucide-vue-next'
import type { TableColumn } from '~/types/dashboard'

const props = defineProps<{
  modelValue: TableColumn
  editMode: boolean
  availableKeys?: string[]
}>()

const datalistId = `col-keys-${Math.random().toString(36).slice(2)}`

const emit = defineEmits<{
  'update:modelValue': [value: TableColumn]
  remove: []
}>()

const NUMERIC_FORMATS = new Set(['number', 'currency', 'percent', 'duration'])
const isNumeric = computed(() => NUMERIC_FORMATS.has(local.format ?? ''))

const local = reactive<TableColumn>({ ...props.modelValue })

watch(
  () => props.modelValue,
  (val) => {
    Object.keys(local).forEach(k => { if (!(k in val)) delete (local as any)[k] })
    Object.assign(local, val)
  },
  { deep: true },
)

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
