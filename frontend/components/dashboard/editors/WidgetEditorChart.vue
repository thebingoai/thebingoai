<template>
  <div class="h-full overflow-y-auto p-5 space-y-5">

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

    <!-- Chart title -->
    <div class="space-y-1.5">
      <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Chart Title</label>
      <input
        v-model="localChartTitle"
        type="text"
        placeholder="Optional chart title"
        class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
        :readonly="!editMode"
        :class="!editMode ? 'cursor-default bg-gray-50' : ''"
        @input="emitDebounced()"
      />
    </div>

    <!-- Options -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Options</h3>

      <div class="space-y-2">
        <label class="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            :checked="localOptions.showLegend !== false"
            :disabled="!editMode"
            class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-300"
            @change="localOptions.showLegend = ($event.target as HTMLInputElement).checked; emitDebounced()"
          />
          <span class="text-sm text-gray-700">Show legend</span>
        </label>

        <label class="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            :checked="localOptions.showGrid !== false"
            :disabled="!editMode"
            class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-300"
            @change="localOptions.showGrid = ($event.target as HTMLInputElement).checked; emitDebounced()"
          />
          <span class="text-sm text-gray-700">Show grid</span>
        </label>

        <label class="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            :checked="localOptions.showTooltips !== false"
            :disabled="!editMode"
            class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-300"
            @change="localOptions.showTooltips = ($event.target as HTMLInputElement).checked; emitDebounced()"
          />
          <span class="text-sm text-gray-700">Show tooltips</span>
        </label>

        <label
          v-if="localType === 'bar' || localType === 'line'"
          class="flex items-center gap-2 cursor-pointer select-none"
        >
          <input
            type="checkbox"
            :checked="localOptions.stacked"
            :disabled="!editMode"
            class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-300"
            @change="localOptions.stacked = ($event.target as HTMLInputElement).checked; emitDebounced()"
          />
          <span class="text-sm text-gray-700">Stacked</span>
        </label>

        <label
          v-if="localType === 'bar'"
          class="flex items-center gap-2 cursor-pointer select-none"
        >
          <input
            type="checkbox"
            :checked="localOptions.indexAxis === 'y'"
            :disabled="!editMode"
            class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-300"
            @change="localOptions.indexAxis = ($event.target as HTMLInputElement).checked ? 'y' : 'x'; emitDebounced()"
          />
          <span class="text-sm text-gray-700">Horizontal bars</span>
        </label>
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
const localType = ref<ChartType>(chartConfig.value.type)
const localChartTitle = ref(chartConfig.value.title ?? '')
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
      title: localChartTitle.value || undefined,
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
