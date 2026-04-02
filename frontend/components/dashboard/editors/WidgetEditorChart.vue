<template>
  <div class="h-full overflow-y-auto p-5 space-y-5">

    <!-- Label -->
    <div class="space-y-1.5">
      <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Label</label>
      <input
        v-model="localTitle"
        type="text"
        placeholder="e.g. Monthly Revenue"
        class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
        :readonly="!editMode"
        :class="!editMode ? 'cursor-default bg-gray-50' : ''"
        @input="emitDebounced()"
      />
    </div>

    <!-- Chart Type -->
    <div class="space-y-2">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Chart Type</h3>
      <div class="grid grid-cols-3 gap-2">
        <button
          v-for="ct in chartTypes"
          :key="ct.value"
          class="flex flex-col items-center gap-1.5 rounded-lg border p-2.5 text-xs font-medium transition-colors"
          :class="localType === ct.value
            ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
            : 'border-gray-200 bg-white text-gray-500 hover:bg-gray-50'"
          :disabled="!editMode"
          @click="editMode && setType(ct.value)"
        >
          <component :is="ct.icon" class="h-4 w-4" />
          {{ ct.label }}
        </button>
      </div>
    </div>

    <!-- Options -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Options</h3>

      <div class="space-y-1">
        <div class="flex items-center justify-between py-1">
          <span class="text-sm text-gray-700">Show legend</span>
          <button
            type="button"
            role="switch"
            :aria-checked="localOptions.showLegend !== false"
            :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="localOptions.showLegend !== false ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && (localOptions.showLegend = !(localOptions.showLegend !== false), emitDebounced())"
          >
            <span
              class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="localOptions.showLegend !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
            />
          </button>
        </div>

        <div class="flex items-center justify-between py-1">
          <span class="text-sm text-gray-700">Show grid</span>
          <button
            type="button"
            role="switch"
            :aria-checked="localOptions.showGrid !== false"
            :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="localOptions.showGrid !== false ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && (localOptions.showGrid = !(localOptions.showGrid !== false), emitDebounced())"
          >
            <span
              class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="localOptions.showGrid !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
            />
          </button>
        </div>

        <div class="flex items-center justify-between py-1">
          <span class="text-sm text-gray-700">Show tooltips</span>
          <button
            type="button"
            role="switch"
            :aria-checked="localOptions.showTooltips !== false"
            :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="localOptions.showTooltips !== false ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && (localOptions.showTooltips = !(localOptions.showTooltips !== false), emitDebounced())"
          >
            <span
              class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="localOptions.showTooltips !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
            />
          </button>
        </div>

        <div class="flex items-center justify-between py-1">
          <span class="text-sm text-gray-700">Show values</span>
          <button
            type="button"
            role="switch"
            :aria-checked="!!localOptions.showValues"
            :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="localOptions.showValues ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && (localOptions.showValues = !localOptions.showValues, emitDebounced())"
          >
            <span
              class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="localOptions.showValues ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
            />
          </button>
        </div>

        <!-- Round values (nested under Show values) -->
        <template v-if="localOptions.showValues">
          <div class="ml-4 border-l-2 border-indigo-100 pl-3 space-y-1">
            <div class="flex items-center justify-between py-1">
              <span class="text-sm text-gray-700">Round values</span>
              <button
                type="button"
                role="switch"
                :aria-checked="!!localOptions.roundValues"
                :disabled="!editMode"
                class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="localOptions.roundValues ? 'bg-indigo-600' : 'bg-gray-200'"
                @click="editMode && (localOptions.roundValues = !localOptions.roundValues, emitDebounced())"
              >
                <span
                  class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                  :class="localOptions.roundValues ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
                />
              </button>
            </div>

            <div v-if="localOptions.roundValues" class="flex items-center justify-between py-1">
              <span class="text-sm text-gray-700">Decimal places</span>
              <input
                v-model.number="localOptions.decimalPlaces"
                type="number"
                min="0"
                max="10"
                class="w-16 rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm text-center text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
                :readonly="!editMode"
                :class="!editMode ? 'cursor-default bg-gray-50' : ''"
                @input="emitDebounced()"
              />
            </div>
          </div>
        </template>

        <div
          v-if="localType === 'bar' || localType === 'line'"
          class="flex items-center justify-between py-1"
        >
          <span class="text-sm text-gray-700">Stacked</span>
          <button
            type="button"
            role="switch"
            :aria-checked="!!localOptions.stacked"
            :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="localOptions.stacked ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && (localOptions.stacked = !localOptions.stacked, emitDebounced())"
          >
            <span
              class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="localOptions.stacked ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
            />
          </button>
        </div>

        <div
          v-if="localType === 'bar'"
          class="flex items-center justify-between py-1"
        >
          <span class="text-sm text-gray-700">Horizontal bars</span>
          <button
            type="button"
            role="switch"
            :aria-checked="localOptions.indexAxis === 'y'"
            :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="localOptions.indexAxis === 'y' ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && (localOptions.indexAxis = localOptions.indexAxis === 'y' ? 'x' : 'y', emitDebounced())"
          >
            <span
              class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="localOptions.indexAxis === 'y' ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
            />
          </button>
        </div>
      </div>
    </div>

    <!-- Sort -->
    <div v-if="localType !== 'scatter'" class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Sort</h3>
      <div class="space-y-2">
        <div class="space-y-1.5">
          <label class="text-[11px] text-gray-500">Sort by</label>
          <select
            v-model="localOptions.sortBy"
            class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :disabled="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50' : ''"
            @change="emitDebounced()"
          >
            <option value="none">None</option>
            <option value="label">Label</option>
            <option value="value">Value</option>
          </select>
        </div>
        <div v-if="localOptions.sortBy && localOptions.sortBy !== 'none'" class="space-y-1.5">
          <label class="text-[11px] text-gray-500">Direction</label>
          <select
            v-model="localOptions.sortDirection"
            class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :disabled="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50' : ''"
            @change="emitDebounced()"
          >
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, h } from 'vue'
import { LineChart, BarChart2, PieChart, TrendingUp } from 'lucide-vue-next'
import type { WidgetConfig, ChartWidgetConfig } from '~/types/dashboard'
import type { ChartType, ChartOptions } from '~/types/chart'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
}>()

const chartConfig = computed(() => props.modelValue.config as ChartWidgetConfig)

// Local state
const localTitle = ref(chartConfig.value.title ?? '')
const localType = ref<ChartType>(chartConfig.value.type)
const localOptions = ref<ChartOptions>(JSON.parse(JSON.stringify(chartConfig.value.options ?? {})))

// Debounced emit (150ms) to avoid rapid store updates while typing
let debounceTimer: ReturnType<typeof setTimeout> | null = null

function emitDebounced() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    emit('update:modelValue', buildConfig())
  }, 150)
}

function buildConfig(): WidgetConfig {
  return {
    type: 'chart',
    config: {
      type: localType.value,
      title: localTitle.value || undefined,
      data: chartConfig.value.data,
      options: Object.keys(localOptions.value).length > 0 ? localOptions.value : undefined,
    },
  }
}

function setType(t: string) {
  localType.value = t as ChartType
  emitDebounced()
}

const DoughnutIcon = {
  render() {
    return h('svg', { xmlns: 'http://www.w3.org/2000/svg', width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
      h('circle', { cx: 12, cy: 12, r: 10 }),
      h('circle', { cx: 12, cy: 12, r: 4 }),
    ])
  },
}

const ScatterIcon = {
  render() {
    return h('svg', { xmlns: 'http://www.w3.org/2000/svg', width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
      h('circle', { cx: 7, cy: 17, r: 1.5, fill: 'currentColor' }),
      h('circle', { cx: 14, cy: 7, r: 1.5, fill: 'currentColor' }),
      h('circle', { cx: 18, cy: 14, r: 1.5, fill: 'currentColor' }),
      h('circle', { cx: 10, cy: 12, r: 1.5, fill: 'currentColor' }),
    ])
  },
}

const chartTypes = [
  { value: 'line', label: 'Line', icon: LineChart },
  { value: 'bar', label: 'Bar', icon: BarChart2 },
  { value: 'pie', label: 'Pie', icon: PieChart },
  { value: 'doughnut', label: 'Doughnut', icon: DoughnutIcon },
  { value: 'area', label: 'Area', icon: TrendingUp },
  { value: 'scatter', label: 'Scatter', icon: ScatterIcon },
]
</script>
