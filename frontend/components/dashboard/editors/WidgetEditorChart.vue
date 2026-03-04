<template>
  <div class="flex h-full">
    <!-- Left: chart editor form -->
    <div class="w-96 flex-shrink-0 border-r border-gray-100 overflow-y-auto p-5 space-y-5">

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

      <!-- Labels -->
      <div class="space-y-1.5">
        <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Labels (one per line)</label>
        <textarea
          v-model="labelsText"
          :readonly="!editMode"
          rows="4"
          class="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs font-mono text-gray-800 leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
          :class="editMode ? 'bg-white' : 'cursor-default'"
          @input="emitDebounced()"
        />
      </div>

      <!-- Datasets -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Datasets</h3>
          <button
            v-if="editMode"
            class="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
            @click="addDataset()"
          >
            <span class="text-base leading-none">+</span> Add Dataset
          </button>
        </div>

        <div class="space-y-3">
          <div
            v-for="(ds, i) in localDatasets"
            :key="i"
            class="rounded-lg border border-gray-200 p-3 space-y-2 bg-gray-50"
          >
            <div class="flex items-center justify-between">
              <span class="text-xs font-medium text-gray-600">Dataset {{ i + 1 }}</span>
              <button
                v-if="editMode && localDatasets.length > 1"
                class="flex h-5 w-5 items-center justify-center rounded text-gray-300 hover:bg-rose-50 hover:text-rose-500 transition-colors"
                @click="removeDataset(i)"
              >
                <X class="h-3.5 w-3.5" />
              </button>
            </div>

            <div class="space-y-1">
              <label class="text-[10px] text-gray-400">Label</label>
              <input
                v-model="ds.label"
                type="text"
                placeholder="Series name"
                class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
                :readonly="!editMode"
                :class="!editMode ? 'cursor-default bg-gray-50' : ''"
                @input="emitDebounced()"
              />
            </div>

            <div class="space-y-1">
              <label class="text-[10px] text-gray-400">Data (one number per line)</label>
              <textarea
                :value="datasetToText(ds.data)"
                :readonly="!editMode"
                rows="3"
                class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-xs font-mono text-gray-800 leading-relaxed resize-none focus:outline-none focus:ring-1 focus:ring-indigo-300"
                :class="!editMode ? 'cursor-default bg-gray-50' : ''"
                @input="onDatasetDataInput(i, ($event.target as HTMLTextAreaElement).value)"
              />
            </div>

            <div class="flex gap-2">
              <div class="flex-1 space-y-1">
                <label class="text-[10px] text-gray-400">Background Color</label>
                <div class="flex gap-1.5">
                  <input
                    :value="toHexColor(ds.backgroundColor)"
                    type="color"
                    :disabled="!editMode"
                    class="h-7 w-8 rounded border border-gray-200 cursor-pointer disabled:cursor-default"
                    @input="onColorInput(i, 'backgroundColor', ($event.target as HTMLInputElement).value)"
                  />
                  <input
                    :value="String(Array.isArray(ds.backgroundColor) ? ds.backgroundColor[0] : ds.backgroundColor ?? '')"
                    type="text"
                    placeholder="#6366f1"
                    class="flex-1 rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
                    :readonly="!editMode"
                    :class="!editMode ? 'cursor-default bg-gray-50' : ''"
                    @input="onColorInput(i, 'backgroundColor', ($event.target as HTMLInputElement).value)"
                  />
                </div>
              </div>
              <div class="flex-1 space-y-1">
                <label class="text-[10px] text-gray-400">Border Color</label>
                <div class="flex gap-1.5">
                  <input
                    :value="toHexColor(ds.borderColor)"
                    type="color"
                    :disabled="!editMode"
                    class="h-7 w-8 rounded border border-gray-200 cursor-pointer disabled:cursor-default"
                    @input="onColorInput(i, 'borderColor', ($event.target as HTMLInputElement).value)"
                  />
                  <input
                    :value="String(Array.isArray(ds.borderColor) ? ds.borderColor[0] : ds.borderColor ?? '')"
                    type="text"
                    placeholder="#6366f1"
                    class="flex-1 rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
                    :readonly="!editMode"
                    :class="!editMode ? 'cursor-default bg-gray-50' : ''"
                    @input="onColorInput(i, 'borderColor', ($event.target as HTMLInputElement).value)"
                  />
                </div>
              </div>
            </div>

            <div class="flex items-center gap-4">
              <label class="flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  :checked="ds.fill"
                  :disabled="!editMode"
                  class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-300"
                  @change="ds.fill = ($event.target as HTMLInputElement).checked; emitDebounced()"
                />
                <span class="text-xs text-gray-600">Fill</span>
              </label>
              <div class="flex-1 space-y-1">
                <label class="text-[10px] text-gray-400">Tension ({{ ds.tension ?? 0 }})</label>
                <input
                  :value="ds.tension ?? 0"
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  :disabled="!editMode"
                  class="w-full"
                  @input="ds.tension = parseFloat(($event.target as HTMLInputElement).value); emitDebounced()"
                />
              </div>
            </div>
          </div>
        </div>
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

    <!-- Right: live preview -->
    <div class="flex-1 overflow-hidden flex flex-col min-w-0">
      <div class="px-4 py-2 border-b border-gray-100 flex-shrink-0">
        <span class="text-[11px] font-medium text-gray-400 uppercase tracking-wide">Preview</span>
      </div>
      <div class="flex-1 overflow-hidden p-4 min-h-0">
        <DashboardWidgetChart :config="debouncedConfig" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h } from 'vue'
import { X, LineChart, BarChart2, PieChart, TrendingUp } from 'lucide-vue-next'
import type { WidgetConfig, ChartWidgetConfig } from '~/types/dashboard'
import type { DatasetConfig, ChartType, ChartOptions } from '~/types/chart'

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
const labelsText = ref((chartConfig.value.data?.labels ?? []).join('\n'))
const localDatasets = ref<DatasetConfig[]>(
  JSON.parse(JSON.stringify(chartConfig.value.data?.datasets ?? [])),
)
const localOptions = ref<ChartOptions>(JSON.parse(JSON.stringify(chartConfig.value.options ?? {})))

// Debounced preview config (150ms)
let debounceTimer: ReturnType<typeof setTimeout> | null = null
const debouncedConfig = ref<ChartWidgetConfig>(JSON.parse(JSON.stringify(chartConfig.value)))

function emitDebounced() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    const config = buildConfig()
    debouncedConfig.value = config.config as ChartWidgetConfig
    emit('update:modelValue', config)
  }, 150)
}

function buildConfig(): WidgetConfig {
  const labels = labelsText.value
    .split('\n')
    .map(s => s.trim())
    .filter(s => s.length > 0)

  return {
    type: 'chart',
    config: {
      type: localType.value,
      title: localChartTitle.value || undefined,
      data: {
        labels,
        datasets: localDatasets.value,
      },
      options: Object.keys(localOptions.value).length > 0 ? localOptions.value : undefined,
    },
  }
}

function setType(t: string) {
  localType.value = t as ChartType
  emitDebounced()
}

function datasetToText(data: number[]): string {
  return (data ?? []).join('\n')
}

function onDatasetDataInput(i: number, text: string) {
  const nums = text
    .split('\n')
    .map(s => parseFloat(s.trim()))
    .filter(n => !isNaN(n))
  localDatasets.value[i].data = nums
  emitDebounced()
}

function onColorInput(i: number, field: 'backgroundColor' | 'borderColor', val: string) {
  localDatasets.value[i][field] = val
  emitDebounced()
}

/** Returns a #rrggbb hex string for use in <input type="color">. Falls back to #000000. */
function toHexColor(val: string | string[] | undefined): string {
  const raw = Array.isArray(val) ? val[0] : val ?? ''
  return /^#[0-9a-fA-F]{6}$/.test(raw) ? raw : '#000000'
}

function addDataset() {
  localDatasets.value.push({
    label: `Series ${localDatasets.value.length + 1}`,
    data: [],
    backgroundColor: '#6366f1',
    borderColor: '#6366f1',
    borderWidth: 1,
  })
  emitDebounced()
}

function removeDataset(i: number) {
  localDatasets.value.splice(i, 1)
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
