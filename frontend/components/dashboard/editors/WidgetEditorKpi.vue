<template>
  <div class="h-full overflow-y-auto p-5 space-y-5">

    <!-- Display section -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Display</h3>

      <div class="space-y-1.5">
        <label class="text-xs text-gray-600">Label</label>
        <input
          v-model="localLabel"
          type="text"
          placeholder="e.g. Total Revenue"
          class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
          :readonly="!editMode"
          :class="!editMode ? 'cursor-default bg-gray-50' : ''"
        />
      </div>

      <!-- Value: split aggregation + column selector when data source exists -->
      <div v-if="dataSource" class="space-y-1.5">
        <label class="text-xs text-gray-600">Value</label>
        <div class="flex">
          <select
            :value="kpiMapping?.aggregation ?? 'first'"
            :disabled="!editMode"
            class="rounded-l-lg rounded-r-none border border-r-0 border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
            @change="onAggregationChange($event)"
          >
            <option value="first">First Row</option>
            <option value="last">Last Row</option>
            <option value="sum">Sum</option>
            <option value="avg">Average</option>
            <option value="count">Count</option>
            <option value="min">Min</option>
            <option value="max">Max</option>
          </select>
          <select
            :value="kpiMapping?.valueColumn || ''"
            :disabled="!editMode"
            class="flex-1 min-w-0 rounded-r-lg rounded-l-none border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
            @change="onValueColumnChange($event)"
          >
            <option value="" disabled>Select column...</option>
            <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
          </select>
        </div>
      </div>

      <!-- Value: manual input when no data source -->
      <div v-else class="space-y-1.5">
        <label class="text-xs text-gray-600">Value</label>
        <input
          v-model="localValue"
          type="text"
          placeholder="e.g. 42000"
          class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
          :readonly="!editMode"
          :class="!editMode ? 'cursor-default bg-gray-50' : ''"
        />
      </div>

      <div class="flex gap-2">
        <div class="flex-1 space-y-1.5">
          <label class="text-xs text-gray-600">Prefix</label>
          <input
            v-model="localPrefix"
            type="text"
            placeholder="e.g. $"
            class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :readonly="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50' : ''"
          />
        </div>
        <div class="flex-1 space-y-1.5">
          <label class="text-xs text-gray-600">Suffix</label>
          <input
            v-model="localSuffix"
            type="text"
            placeholder="e.g. %"
            class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :readonly="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50' : ''"
          />
        </div>
      </div>

      <!-- Round value -->
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Round value</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localRoundValue"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localRoundValue ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && (localRoundValue = !localRoundValue)"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localRoundValue ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <div v-if="localRoundValue" class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Decimal places</span>
        <input
          v-model.number="localDecimalPlaces"
          type="number"
          min="0"
          max="10"
          class="w-16 rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm text-center text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
          :readonly="!editMode"
          :class="!editMode ? 'cursor-default bg-gray-50' : ''"
        />
      </div>
    </div>

    <!-- Trend section -->
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Trend</h3>
        <button
          type="button"
          role="switch"
          :aria-checked="hasTrend"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="hasTrend ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggleTrend()"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="hasTrend ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <template v-if="hasTrend">
        <!-- Auto-calculated info (when data source with autoTrend) -->
        <div v-if="isAutoTrend" class="rounded-lg bg-gray-100 px-3 py-2">
          <p class="text-[11px] text-gray-500">
            Trend is auto-calculated from your query results. Select a period and date column below to control the comparison.
          </p>
        </div>

        <!-- Pre-computed info (when data source without autoTrend) -->
        <div v-else-if="dataSource && kpiMapping?.trendValueColumn" class="rounded-lg bg-gray-100 px-3 py-2">
          <p class="text-[11px] text-gray-500">
            Trend value comes from the <code class="bg-gray-200 px-1 rounded text-[10px]">{{ kpiMapping.trendValueColumn }}</code> column in your query.
          </p>
        </div>

        <!-- Manual fields (no data source — static KPI) -->
        <template v-if="!dataSource">
          <div class="space-y-1.5">
            <label class="text-xs text-gray-600">Direction</label>
            <select
              v-model="localTrendDirection"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
            >
              <option value="up">Up</option>
              <option value="down">Down</option>
              <option value="neutral">Neutral</option>
            </select>
          </div>

          <div class="space-y-1.5">
            <label class="text-xs text-gray-600">Value (%)</label>
            <input
              v-model.number="localTrendValue"
              type="number"
              placeholder="e.g. 12.5"
              class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
              :readonly="!editMode"
              :class="!editMode ? 'cursor-default bg-gray-50' : ''"
            />
          </div>
        </template>

        <!-- Period dropdown (always shown when trend is enabled) -->
        <div class="space-y-1.5">
          <label class="text-xs text-gray-600">Period</label>
          <select
            v-model="localTrendPeriod"
            :disabled="!editMode"
            class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
          >
            <option value="">None</option>
            <option value="vs last period">vs last period</option>
            <option value="vs yesterday">vs yesterday</option>
            <option value="vs last week">vs last week</option>
            <option value="vs last month">vs last month</option>
            <option value="vs last quarter">vs last quarter</option>
            <option value="vs last year">vs last year</option>
            <option value="__custom__">Custom...</option>
          </select>
          <input
            v-if="localTrendPeriod === '__custom__'"
            v-model="customTrendPeriod"
            type="text"
            placeholder="e.g. vs previous sprint"
            class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :readonly="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50' : ''"
          />
        </div>

        <!-- Date column picker (needed for period-based comparison) -->
        <div v-if="needsDateColumn && sourceColumns && sourceColumns.length > 0" class="space-y-1.5">
          <label class="text-xs text-gray-600">Date column</label>
          <select
            :value="kpiMapping?.trendDateColumn || ''"
            :disabled="!editMode"
            class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
            @change="editMode && emit('update:mapping', { trendDateColumn: ($event.target as HTMLSelectElement).value || undefined })"
          >
            <option value="">Select date column...</option>
            <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
          </select>
        </div>
      </template>
    </div>

    <!-- Sparkline section -->
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Sparkline</h3>
        <button
          type="button"
          role="switch"
          :aria-checked="hasSparkline"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="hasSparkline ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggleSparkline()"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="hasSparkline ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <template v-if="hasSparkline">
        <!-- Auto-calculated suggestion (when data source with autoTrend) -->
        <div v-if="isAutoTrend" class="rounded-lg bg-indigo-50 border border-indigo-100 px-3 py-2 space-y-1">
          <p class="text-[11px] text-indigo-600">
            Sparkline is auto-populated from all rows using the
            <code class="bg-indigo-100 px-1 rounded text-[10px]">{{ kpiMapping?.valueColumn }}</code> column.
          </p>
          <p class="text-[10px] text-indigo-400">
            Ensure your query returns rows ordered by time period for an accurate chart.
          </p>
        </div>

        <!-- X/Y axis column selectors (when columns are available) -->
        <template v-if="sourceColumns && sourceColumns.length > 0">
          <div class="space-y-2">
            <div class="space-y-1">
              <label class="text-xs text-gray-600">X Axis (labels)</label>
              <select
                :value="kpiMapping?.sparklineXColumn || ''"
                :disabled="!editMode"
                class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
                @change="editMode && emit('update:mapping', { sparklineXColumn: ($event.target as HTMLSelectElement).value || undefined })"
              >
                <option value="">None</option>
                <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
              </select>
            </div>
            <div class="space-y-1">
              <label class="text-xs text-gray-600">Y Axis (values)</label>
              <select
                :value="kpiMapping?.sparklineYColumn || ''"
                :disabled="!editMode"
                class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
                @change="editMode && emit('update:mapping', { sparklineYColumn: ($event.target as HTMLSelectElement).value || undefined })"
              >
                <option value="" disabled>Select column...</option>
                <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
              </select>
            </div>
            <div class="space-y-1">
              <label class="text-xs text-gray-600">Sort by</label>
              <div class="flex">
                <select
                  :value="kpiMapping?.sparklineSortDirection ?? 'asc'"
                  :disabled="!editMode"
                  class="rounded-l-lg rounded-r-none border border-r-0 border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
                  @change="editMode && emit('update:mapping', { sparklineSortDirection: ($event.target as HTMLSelectElement).value })"
                >
                  <option value="asc">ASC</option>
                  <option value="desc">DESC</option>
                </select>
                <select
                  :value="kpiMapping?.sparklineSortColumn || ''"
                  :disabled="!editMode"
                  class="flex-1 min-w-0 rounded-r-lg rounded-l-none border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
                  @change="editMode && emit('update:mapping', { sparklineSortColumn: ($event.target as HTMLSelectElement).value || undefined })"
                >
                  <option value="">None (query order)</option>
                  <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
                </select>
              </div>
            </div>
          </div>
        </template>

        <!-- Manual input (no data source — static KPI) -->
        <div v-if="!dataSource" class="space-y-1.5">
          <label class="text-xs text-gray-600">Data (comma-separated numbers)</label>
          <input
            v-model="sparklineInput"
            type="text"
            placeholder="e.g. 10,20,15,30,25"
            class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :readonly="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50' : ''"
          />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { WidgetConfig, KpiWidgetConfig, WidgetDataSource, KpiDataSourceMapping } from '~/types/dashboard'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
  dataSource?: WidgetDataSource
  sourceColumns?: string[]
  sourceRows?: any[][]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
  'update:mapping': [patch: Record<string, any>]
}>()

const kpiConfig = () => props.modelValue.config as KpiWidgetConfig

const kpiMapping = computed(() => {
  if (props.dataSource?.mapping?.type === 'kpi') {
    return props.dataSource.mapping as KpiDataSourceMapping
  }
  return null
})

const isAutoTrend = computed(() => !!kpiMapping.value?.autoTrend)

// Periods that require a date column for comparison (not simple last-two-rows)
const DATE_BASED_PERIODS = new Set(['vs yesterday', 'vs last week', 'vs last month', 'vs last quarter', 'vs last year'])

// Local state mirroring config
const localLabel = ref(kpiConfig().label)
const localValue = ref(String(kpiConfig().value))
const localPrefix = ref(kpiConfig().prefix ?? '')
const localSuffix = ref(kpiConfig().suffix ?? '')
const localRoundValue = ref(!!kpiConfig().roundValue)
const localDecimalPlaces = ref(kpiConfig().decimalPlaces ?? 2)
const hasTrend = ref(!!kpiConfig().trend)
const localTrendDirection = ref<'up' | 'down' | 'neutral'>(kpiConfig().trend?.direction ?? 'up')
const localTrendValue = ref(kpiConfig().trend?.value ?? 0)
const hasSparkline = ref(!!(kpiConfig().sparkline?.length))
const sparklineInput = ref((kpiConfig().sparkline ?? []).join(', '))

// Period: check if current value matches a preset, otherwise use custom
const PERIOD_PRESETS = ['', 'vs last period', 'vs yesterday', 'vs last week', 'vs last month', 'vs last quarter', 'vs last year']
const initPeriod = kpiConfig().trend?.period ?? kpiMapping.value?.periodLabel ?? ''
const isPreset = PERIOD_PRESETS.includes(initPeriod)
const localTrendPeriod = ref(isPreset ? initPeriod : '__custom__')
const customTrendPeriod = ref(isPreset ? '' : initPeriod)

// Compute the effective period label
const effectivePeriod = computed(() => {
  if (localTrendPeriod.value === '__custom__') return customTrendPeriod.value
  return localTrendPeriod.value
})

// Show date column picker when a date-based period is selected
const needsDateColumn = computed(() => DATE_BASED_PERIODS.has(effectivePeriod.value))

// Flag to prevent resync from reverting our own emits
let selfEmit = false

// Recompute aggregated value when source rows arrive or mapping changes
watch(
  [() => props.sourceRows, () => kpiMapping.value?.aggregation, () => kpiMapping.value?.valueColumn],
  () => {
    const agg = kpiMapping.value?.aggregation
    const col = kpiMapping.value?.valueColumn
    if (agg && agg !== 'first' && col && props.sourceRows?.length && props.sourceColumns?.length) {
      recomputeValue(col, agg)
    }
  },
)

// Resync local state when the parent switches widget or data source changes
watch([() => props.modelValue, () => props.dataSource], () => {
  if (selfEmit) return
  const cfg = kpiConfig()
  localLabel.value = cfg.label
  localValue.value = String(cfg.value)
  localPrefix.value = cfg.prefix ?? ''
  localSuffix.value = cfg.suffix ?? ''
  localRoundValue.value = !!cfg.roundValue
  localDecimalPlaces.value = cfg.decimalPlaces ?? 2
  hasTrend.value = !!cfg.trend
  localTrendDirection.value = cfg.trend?.direction ?? 'up'
  localTrendValue.value = cfg.trend?.value ?? 0
  hasSparkline.value = !!(cfg.sparkline?.length)
  sparklineInput.value = (cfg.sparkline ?? []).join(', ')

  const period = cfg.trend?.period ?? kpiMapping.value?.periodLabel ?? ''
  const preset = PERIOD_PRESETS.includes(period)
  localTrendPeriod.value = preset ? period : '__custom__'
  customTrendPeriod.value = preset ? '' : period
})

function buildConfig(): WidgetConfig {
  const parsedValue = isNaN(Number(localValue.value)) ? localValue.value : Number(localValue.value)
  const sparklineNums = sparklineInput.value
    .split(',')
    .map(s => parseFloat(s.trim()))
    .filter(n => !isNaN(n))

  // Preserve backend-populated data when data source columns are configured
  const existingConfig = kpiConfig()
  const hasDataSourceTrend = isAutoTrend.value || !!kpiMapping.value?.trendValueColumn
  const hasDataSourceSparkline = isAutoTrend.value || !!kpiMapping.value?.sparklineYColumn

  const trend = hasTrend.value
    ? hasDataSourceTrend
      ? { ...existingConfig.trend, period: effectivePeriod.value || undefined }
      : { direction: localTrendDirection.value, value: localTrendValue.value, period: effectivePeriod.value || undefined }
    : undefined

  const sparkline = hasSparkline.value
    ? hasDataSourceSparkline
      ? existingConfig.sparkline // keep what the backend wrote
      : sparklineNums.length > 0 ? sparklineNums : undefined
    : undefined

  return {
    type: 'kpi',
    config: {
      label: localLabel.value,
      value: props.dataSource
        ? (kpiMapping.value?.aggregation && kpiMapping.value.aggregation !== 'first' ? parsedValue : existingConfig.value)
        : parsedValue,
      prefix: localPrefix.value || undefined,
      suffix: localSuffix.value || undefined,
      roundValue: localRoundValue.value || undefined,
      decimalPlaces: localRoundValue.value ? localDecimalPlaces.value : undefined,
      trend,
      sparkline,
    },
  }
}

// Emit on any local field change — set flag to skip resync from our own emit
watch(
  [localLabel, localValue, localPrefix, localSuffix, localRoundValue, localDecimalPlaces, hasTrend, localTrendDirection, localTrendValue, localTrendPeriod, customTrendPeriod, hasSparkline, sparklineInput],
  () => {
    selfEmit = true
    emit('update:modelValue', buildConfig())
    nextTick(() => { selfEmit = false })
  },
)

// Sync period label into the data source mapping so it persists across refreshes
watch(effectivePeriod, () => {
  if (props.dataSource && hasTrend.value) {
    emit('update:mapping', { periodLabel: effectivePeriod.value || undefined })
  }
})

function toggleTrend() {
  hasTrend.value = !hasTrend.value
}

function toggleSparkline() {
  hasSparkline.value = !hasSparkline.value
}


function computeAggregatedValue(
  rows: any[][],
  columns: string[],
  valueColumn: string,
  aggregation: string,
): any {
  const colIdx = columns.indexOf(valueColumn)
  if (colIdx === -1 || !rows.length) return null

  const nums = rows.map(r => r[colIdx]).filter((v): v is number => typeof v === 'number')
  if (!nums.length) return rows[0]?.[colIdx] ?? null

  switch (aggregation) {
    case 'sum': return nums.reduce((a, b) => a + b, 0)
    case 'avg': return Math.round((nums.reduce((a, b) => a + b, 0) / nums.length) * 100) / 100
    case 'count': return nums.length
    case 'min': return Math.min(...nums)
    case 'max': return Math.max(...nums)
    case 'last': return nums[nums.length - 1]
    default: return nums[0] // 'first'
  }
}

function recomputeValue(valueColumn: string, aggregation: string) {
  if (!props.sourceColumns?.length || !props.sourceRows?.length) return
  const newValue = computeAggregatedValue(props.sourceRows, props.sourceColumns, valueColumn, aggregation)
  if (newValue !== null) {
    localValue.value = String(newValue)
  }
}

function onValueColumnChange(event: Event) {
  const col = (event.target as HTMLSelectElement).value
  emit('update:mapping', { valueColumn: col })
  recomputeValue(col, kpiMapping.value?.aggregation ?? 'first')
}

function onAggregationChange(event: Event) {
  const agg = (event.target as HTMLSelectElement).value
  emit('update:mapping', { aggregation: agg })
  recomputeValue(kpiMapping.value?.valueColumn ?? '', agg)
}
</script>
