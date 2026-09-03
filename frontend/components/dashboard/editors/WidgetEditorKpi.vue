<template>
  <div class="h-full overflow-y-auto p-5 space-y-5 [&>*+*]:border-t [&>*+*]:border-gray-200 dark:[&>*+*]:border-neutral-700 [&>*+*]:pt-5">

    <!-- Display section -->
    <div class="space-y-3">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Display</h3>

      <div class="space-y-1.5">
        <label class="text-sm text-gray-600 dark:text-neutral-400">Label</label>
        <input
          v-model="localLabel"
          type="text"
          placeholder="e.g. Total Revenue"
          class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
          :readonly="!editMode"
          :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
        />
      </div>

      <!-- Primary field: Dimension / Metric role + column + (metric only) aggregation -->
      <template v-if="dataSource">
        <div class="space-y-1.5">
          <label class="text-sm text-gray-600 dark:text-neutral-400">Primary field</label>
          <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
            <button
              v-for="r in (['dimension', 'metric'] as const)"
              :key="r"
              type="button"
              :disabled="!editMode"
              class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="primaryRole === r
                ? 'bg-indigo-600 text-white'
                : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
              @click="editMode && setPrimaryRole(r)"
            >{{ r === 'dimension' ? 'Dimension' : 'Metric' }}</button>
          </div>
          <p class="text-sm text-gray-400 dark:text-neutral-500 mt-1">
            {{ primaryRole === 'dimension'
              ? 'Shows the raw value from a single row (no aggregation).'
              : 'Aggregates the selected column across all rows.' }}
          </p>
        </div>

        <div
          v-if="!kpiMapping?.valueColumn"
          class="rounded-lg border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300"
        >
          Select a field to display data.
        </div>
        <div class="space-y-1.5">
          <label class="text-sm text-gray-600 dark:text-neutral-400">Field</label>
          <select
            :value="kpiMapping?.valueColumn || ''"
            :disabled="!editMode"
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @change="onValueColumnChange($event)"
          >
            <option value="" disabled>Select column...</option>
            <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
          </select>
        </div>

        <div v-if="primaryRole === 'metric'" class="space-y-1.5">
          <label class="text-sm text-gray-600 dark:text-neutral-400">Aggregation</label>
          <select
            :value="kpiMapping?.aggregation ?? 'sum'"
            :disabled="!editMode"
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @change="onAggregationChange($event)"
          >
            <option value="sum">Sum</option>
            <option value="avg">Average</option>
            <option value="count">Count</option>
            <option value="countDistinct">Count Distinct</option>
            <option value="min">Min</option>
            <option value="max">Max</option>
          </select>
        </div>

        <div v-else class="space-y-1.5">
          <label class="text-sm text-gray-600 dark:text-neutral-400">Row</label>
          <select
            :value="kpiMapping?.aggregation === 'last' ? 'last' : 'first'"
            :disabled="!editMode"
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @change="onAggregationChange($event)"
          >
            <option value="first">First Row</option>
            <option value="last">Last Row</option>
          </select>
        </div>
      </template>

      <!-- Value: manual input when no data source -->
      <div v-else class="space-y-1.5">
        <label class="text-sm text-gray-600 dark:text-neutral-400">Value</label>
        <input
          v-model="localValue"
          type="text"
          placeholder="e.g. 42000"
          class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
          :readonly="!editMode"
          :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
        />
      </div>

      <div class="flex gap-2">
        <div class="flex-1 space-y-1.5">
          <label class="text-sm text-gray-600 dark:text-neutral-400">Prefix</label>
          <input
            v-model="localPrefix"
            type="text"
            placeholder="e.g. $"
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :readonly="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
          />
        </div>
        <div class="flex-1 space-y-1.5">
          <label class="text-sm text-gray-600 dark:text-neutral-400">Suffix</label>
          <input
            v-model="localSuffix"
            type="text"
            placeholder="e.g. %"
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :readonly="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
          />
        </div>
      </div>

      <FieldFormatControls
        :model-value="{ format: localFormat, decimalPlaces: localDecimalPlaces }"
        :edit-mode="editMode"
        show-format
        show-decimals
        @update:model-value="onFormatUpdate"
      />
    </div>

    <!-- Comparison section (replaces Trend) -->
    <div class="space-y-3">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Comparison</h3>

      <!-- Type selector -->
      <div class="space-y-1.5">
        <label class="text-sm text-gray-600 dark:text-neutral-400">Type</label>
        <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
          <button
            v-for="opt in availableComparisonTypes"
            :key="opt.value"
            type="button"
            :disabled="!editMode || opt.disabled"
            :title="opt.disabled ? opt.reason : undefined"
            class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:cursor-not-allowed"
            :class="[
              localComparisonType === opt.value && !opt.disabled
                ? 'bg-indigo-600 text-white'
                : opt.disabled
                  ? 'bg-gray-50 dark:bg-neutral-900 text-gray-300 dark:text-neutral-600'
                  : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800',
            ]"
            @click="editMode && !opt.disabled && setComparisonType(opt.value)"
          >{{ opt.label }}</button>
        </div>
        <p v-if="availableComparisonTypes.some(o => o.disabled)" class="text-sm text-gray-400 dark:text-neutral-500">
          Greyed options need a different query shape. Hover for details.
        </p>
      </div>

      <!-- Period options -->
      <template v-if="localComparisonType === 'period'">
        <!-- Auto-calculated info -->
        <div v-if="isAutoTrend" class="rounded-lg bg-gray-100 dark:bg-neutral-700 px-3 py-2">
          <p class="text-sm text-gray-500 dark:text-neutral-400">
            Comparison is auto-calculated from your query. Select a period and date column to control it.
          </p>
        </div>

        <div class="space-y-1.5">
          <label class="text-sm text-gray-600 dark:text-neutral-400">Period</label>
          <select
            v-model="localTrendPeriod"
            :disabled="!editMode"
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
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
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :readonly="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
          />
        </div>

        <!-- Date column picker -->
        <div v-if="needsDateColumn && sourceColumns?.length" class="space-y-1.5">
          <label class="text-sm text-gray-600 dark:text-neutral-400">Date column</label>
          <select
            :value="kpiMapping?.trendDateColumn || ''"
            :disabled="!editMode"
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @change="editMode && emit('update:mapping', { trendDateColumn: ($event.target as HTMLSelectElement).value || undefined })"
          >
            <option value="">Select date column...</option>
            <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
          </select>
        </div>

        <!-- Manual direction/value for static (no data source) scorecards -->
        <template v-if="!dataSource">
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400">Direction</label>
            <select
              v-model="localTrendDirection"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            >
              <option value="up">Up</option>
              <option value="down">Down</option>
              <option value="neutral">Neutral</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400">Change (%)</label>
            <input
              v-model.number="localTrendValue"
              type="number"
              placeholder="e.g. 12.5"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
              :readonly="!editMode"
              :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
            />
          </div>
        </template>
      </template>

      <!-- Value options -->
      <template v-if="localComparisonType === 'value'">
        <div class="space-y-1.5">
          <label class="text-sm text-gray-600 dark:text-neutral-400">Target value</label>
          <input
            v-model.number="localTargetValue"
            type="number"
            placeholder="e.g. 10000"
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :readonly="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
          />
        </div>
      </template>

      <!-- Metric options -->
      <template v-if="localComparisonType === 'metric'">
        <div class="space-y-1.5">
          <label class="text-sm text-gray-600 dark:text-neutral-400">Target metric column</label>
          <select
            v-model="localTargetMetric"
            :disabled="!editMode"
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
          >
            <option value="">Select column...</option>
            <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
          </select>
        </div>
      </template>

      <!-- Show as progress (available for Value and Metric types) -->
      <template v-if="localComparisonType === 'value' || localComparisonType === 'metric'">
        <div class="flex items-center justify-between py-1">
          <div>
            <span class="text-sm text-gray-700 dark:text-neutral-200">Show as progress</span>
            <p class="text-sm text-gray-400 dark:text-neutral-500 mt-0.5">Renders a progress bar/circle instead of % change</p>
          </div>
          <button
            type="button"
            role="switch"
            :aria-checked="localShowAsProgress"
            :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="localShowAsProgress ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
            @click="editMode && (localShowAsProgress = !localShowAsProgress)"
          >
            <span
              class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="localShowAsProgress ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
            />
          </button>
        </div>

        <div v-if="localShowAsProgress" class="space-y-1.5">
          <label class="text-sm text-gray-600 dark:text-neutral-400">Starting value</label>
          <input
            v-model.number="localStartingValue"
            type="number"
            placeholder="e.g. 0"
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :readonly="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
          />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { WidgetConfig, KpiWidgetConfig, WidgetDataSource, KpiDataSourceMapping } from '~/types/dashboard'
import { countDistinct } from '~/utils/widgetTransform'
import FieldFormatControls from './FieldFormatControls.vue'

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

// Primary-field role: persisted on mapping; back-compat infer from aggregation type
const DIMENSION_AGGS = new Set(['first', 'last'])
const primaryRole = computed<'dimension' | 'metric'>(() => {
  const m = kpiMapping.value
  if (m?.role) return m.role
  return DIMENSION_AGGS.has(m?.aggregation ?? '') ? 'dimension' : 'metric'
})

function setPrimaryRole(r: 'dimension' | 'metric') {
  const m = kpiMapping.value
  const currentAgg = m?.aggregation
  const patch: Record<string, any> = { role: r }
  if (r === 'dimension' && (!currentAgg || !DIMENSION_AGGS.has(currentAgg))) {
    patch.aggregation = 'first'
  } else if (r === 'metric' && DIMENSION_AGGS.has(currentAgg ?? '')) {
    patch.aggregation = 'sum'
  }
  emit('update:mapping', patch)
  if (patch.aggregation) {
    recomputeValue(m?.valueColumn ?? '', patch.aggregation)
  }
}

const DATE_BASED_PERIODS = new Set(['vs yesterday', 'vs last week', 'vs last month', 'vs last quarter', 'vs last year'])

const DATE_COL_RE = /date|time|day|month|year|week|created|updated|period|timestamp|_ts|_at$/i

// Smart-detect which comparison types are usable given current query shape
const availableComparisonTypes = computed(() => {
  const hasPeriod = !props.dataSource
    || isAutoTrend.value
    || ((props.sourceRows?.length ?? 0) >= 2 && (props.sourceColumns ?? []).some(c => DATE_COL_RE.test(c)))

  const hasMetric = !!props.dataSource && (props.sourceColumns?.length ?? 0) >= 2

  return [
    { value: 'none' as const, label: 'None', disabled: false, reason: '' },
    { value: 'period' as const, label: 'Period', disabled: !hasPeriod, reason: 'Needs a date column + multiple rows in your query' },
    { value: 'value' as const, label: 'Value', disabled: false, reason: '' },
    { value: 'metric' as const, label: 'Metric', disabled: !hasMetric, reason: props.dataSource ? 'Needs ≥ 2 columns in your query' : 'Needs a data source' },
  ]
})

// Auto-reset if current type becomes incompatible with query shape
watch(availableComparisonTypes, (opts) => {
  const opt = opts.find(o => o.value === localComparisonType.value)
  if (opt?.disabled) localComparisonType.value = 'none'
})

// Back-compat: existing `trend` field maps to comparison.type = 'period'
function resolveComparisonType(): 'none' | 'period' | 'value' | 'metric' {
  const cfg = kpiConfig()
  if (cfg.comparison) return cfg.comparison.type
  if (cfg.trend) return 'period'
  return 'none'
}

const localLabel = ref(kpiConfig().label)
const localValue = ref(String(kpiConfig().value))
const localPrefix = ref(kpiConfig().prefix ?? '')
const localSuffix = ref(kpiConfig().suffix ?? '')
const localFormat = ref(kpiConfig().format ?? '')
const localDecimalPlaces = ref<number | undefined>(kpiConfig().decimalPlaces)

function onFormatUpdate(patch: { format?: string; decimalPlaces?: number }) {
  if ('format' in patch) localFormat.value = patch.format ?? ''
  if ('decimalPlaces' in patch) localDecimalPlaces.value = patch.decimalPlaces
}
const localComparisonType = ref(resolveComparisonType())
const localTrendDirection = ref<'up' | 'down' | 'neutral'>(kpiConfig().trend?.direction ?? 'up')
const localTrendValue = ref(kpiConfig().trend?.value ?? 0)
const localTargetValue = ref<number | undefined>(kpiConfig().comparison?.targetValue)
const localTargetMetric = ref(kpiConfig().comparison?.targetMetric ?? '')
const localShowAsProgress = ref(!!kpiConfig().comparison?.showAsProgress)
const localStartingValue = ref<number | undefined>(kpiConfig().comparison?.startingValue)

const PERIOD_PRESETS = ['', 'vs last period', 'vs yesterday', 'vs last week', 'vs last month', 'vs last quarter', 'vs last year']
const initPeriod = kpiConfig().comparison?.comparisonLabel ?? kpiConfig().trend?.period ?? kpiMapping.value?.periodLabel ?? ''
const isPreset = PERIOD_PRESETS.includes(initPeriod)
const localTrendPeriod = ref(isPreset ? initPeriod : '__custom__')
const customTrendPeriod = ref(isPreset ? '' : initPeriod)

const effectivePeriod = computed(() => {
  if (localTrendPeriod.value === '__custom__') return customTrendPeriod.value
  return localTrendPeriod.value
})

const needsDateColumn = computed(() => DATE_BASED_PERIODS.has(effectivePeriod.value))

function setComparisonType(type: 'none' | 'period' | 'value' | 'metric') {
  localComparisonType.value = type
  if (type !== 'value' && type !== 'metric') {
    localShowAsProgress.value = false
  }
}

let selfEmit = false

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

watch([() => props.modelValue, () => props.dataSource], () => {
  if (selfEmit) return
  const cfg = kpiConfig()
  localLabel.value = cfg.label
  localValue.value = String(cfg.value)
  localPrefix.value = cfg.prefix ?? ''
  localSuffix.value = cfg.suffix ?? ''
  localFormat.value = cfg.format ?? ''
  localDecimalPlaces.value = cfg.decimalPlaces
  localComparisonType.value = resolveComparisonType()
  localTrendDirection.value = cfg.trend?.direction ?? 'up'
  localTrendValue.value = cfg.trend?.value ?? 0
  localTargetValue.value = cfg.comparison?.targetValue
  localTargetMetric.value = cfg.comparison?.targetMetric ?? ''
  localShowAsProgress.value = !!cfg.comparison?.showAsProgress
  localStartingValue.value = cfg.comparison?.startingValue

  const period = cfg.comparison?.comparisonLabel ?? cfg.trend?.period ?? kpiMapping.value?.periodLabel ?? ''
  const preset = PERIOD_PRESETS.includes(period)
  localTrendPeriod.value = preset ? period : '__custom__'
  customTrendPeriod.value = preset ? '' : period
})

function buildConfig(): WidgetConfig {
  const parsedValue = isNaN(Number(localValue.value)) ? localValue.value : Number(localValue.value)

  const existingConfig = kpiConfig()

  // Build comparison block
  let comparison: KpiWidgetConfig['comparison']
  if (localComparisonType.value !== 'none') {
    const existingComp = existingConfig.comparison ?? {}
    comparison = {
      ...existingComp,
      type: localComparisonType.value,
      ...(localComparisonType.value === 'period' && {
        comparisonLabel: effectivePeriod.value || undefined,
      }),
      ...(localComparisonType.value === 'value' && {
        targetValue: localTargetValue.value,
      }),
      ...(localComparisonType.value === 'metric' && {
        targetMetric: localTargetMetric.value || undefined,
      }),
      ...((localComparisonType.value === 'value' || localComparisonType.value === 'metric') && {
        showAsProgress: localShowAsProgress.value || undefined,
        startingValue: localShowAsProgress.value ? localStartingValue.value : undefined,
      }),
    }
  }

  // Keep legacy `trend` in sync for back-compat with any old renderer that reads it
  const trend = localComparisonType.value === 'period' && !props.dataSource
    ? { direction: localTrendDirection.value, value: localTrendValue.value, period: effectivePeriod.value || undefined }
    : undefined

  return {
    type: 'kpi',
    config: {
      ...existingConfig,
      label: localLabel.value,
      value: props.dataSource
        ? (kpiMapping.value?.aggregation && kpiMapping.value.aggregation !== 'first' ? parsedValue : existingConfig.value)
        : parsedValue,
      prefix: localPrefix.value || undefined,
      suffix: localSuffix.value || undefined,
      format: (localFormat.value || undefined) as KpiWidgetConfig['format'],
      decimalPlaces: localDecimalPlaces.value,
      trend,
      comparison,
    },
  }
}

watch(
  [localLabel, localValue, localPrefix, localSuffix, localFormat, localDecimalPlaces, localComparisonType, localTrendDirection, localTrendValue, localTrendPeriod, customTrendPeriod, localTargetValue, localTargetMetric, localShowAsProgress, localStartingValue],
  () => {
    selfEmit = true
    emit('update:modelValue', buildConfig())
    nextTick(() => { selfEmit = false })
  },
)

watch(effectivePeriod, () => {
  if (props.dataSource && localComparisonType.value === 'period') {
    emit('update:mapping', { periodLabel: effectivePeriod.value || undefined })
  }
})

function computeAggregatedValue(
  rows: any[][],
  columns: string[],
  valueColumn: string,
  aggregation: string,
): any {
  const colIdx = columns.indexOf(valueColumn)
  if (colIdx === -1 || !rows.length) return null
  // Count Distinct works on any value type (not just numbers). Shared with the
  // refresh transform so the editor's optimistic recompute and the server agree
  // on structured cells, which a plain Set counts by reference.
  if (aggregation === 'countDistinct') return countDistinct(rows.map(r => r[colIdx]))
  if (aggregation === 'count') {
    return rows.reduce((acc, r) => acc + (r[colIdx] !== null && r[colIdx] !== undefined ? 1 : 0), 0)
  }
  // First/Last are row picks, not numeric aggregations — return the raw cell
  // (a dimension's first row may legitimately be non-numeric).
  if (aggregation === 'first') return rows[0]?.[colIdx] ?? null
  if (aggregation === 'last') return rows[rows.length - 1]?.[colIdx] ?? null
  const nums = rows.map(r => r[colIdx]).filter((v): v is number => typeof v === 'number')
  if (!nums.length) return rows[0]?.[colIdx] ?? null
  switch (aggregation) {
    case 'sum': return nums.reduce((a, b) => a + b, 0)
    // Raw average — display formatting (decimalPlaces) owns rounding
    case 'avg': return nums.reduce((a, b) => a + b, 0) / nums.length
    case 'min': return Math.min(...nums)
    case 'max': return Math.max(...nums)
    default: return nums[0]
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
  const existingAgg = kpiMapping.value?.aggregation
  // Persist the aggregation the UI displays as default — otherwise the editor
  // shows "Sum" while the backend transform falls back to first-row.
  const agg = existingAgg ?? (primaryRole.value === 'metric' ? 'sum' : 'first')
  emit('update:mapping', existingAgg ? { valueColumn: col } : { valueColumn: col, aggregation: agg })
  recomputeValue(col, agg)
}

function onAggregationChange(event: Event) {
  const agg = (event.target as HTMLSelectElement).value
  emit('update:mapping', { aggregation: agg })
  recomputeValue(kpiMapping.value?.valueColumn ?? '', agg)
}
</script>
