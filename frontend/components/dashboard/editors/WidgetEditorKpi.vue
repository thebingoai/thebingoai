<template>
  <div class="flex h-full">
    <!-- Left: form -->
    <div class="w-80 flex-shrink-0 border-r border-gray-100 overflow-y-auto p-5 space-y-5">

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

        <div class="space-y-1.5">
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
      </div>

      <!-- Trend section -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Trend</h3>
          <button
            class="text-xs font-medium transition-colors"
            :class="hasTrend ? 'text-indigo-600 hover:text-indigo-800' : 'text-gray-400 hover:text-gray-600'"
            :disabled="!editMode"
            @click="editMode && toggleTrend()"
          >
            {{ hasTrend ? 'Enabled' : 'Disabled' }}
          </button>
        </div>

        <template v-if="hasTrend">
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

          <div class="flex gap-2">
            <div class="flex-1 space-y-1.5">
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
            <div class="flex-1 space-y-1.5">
              <label class="text-xs text-gray-600">Period</label>
              <input
                v-model="localTrendPeriod"
                type="text"
                placeholder="e.g. vs last month"
                class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
                :readonly="!editMode"
                :class="!editMode ? 'cursor-default bg-gray-50' : ''"
              />
            </div>
          </div>
        </template>
      </div>

      <!-- Sparkline section -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Sparkline</h3>
          <button
            class="text-xs font-medium transition-colors"
            :class="hasSparkline ? 'text-indigo-600 hover:text-indigo-800' : 'text-gray-400 hover:text-gray-600'"
            :disabled="!editMode"
            @click="editMode && toggleSparkline()"
          >
            {{ hasSparkline ? 'Enabled' : 'Disabled' }}
          </button>
        </div>

        <template v-if="hasSparkline">
          <div class="space-y-1.5">
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

    <!-- Right: live preview -->
    <div class="flex-1 overflow-hidden flex flex-col">
      <div class="px-4 py-2 border-b border-gray-100 flex-shrink-0">
        <span class="text-[11px] font-medium text-gray-400 uppercase tracking-wide">Preview</span>
      </div>
      <div class="flex-1 flex items-center justify-center p-8 overflow-auto min-h-0">
        <div class="w-64 h-36 border border-gray-200 rounded-xl overflow-hidden shadow-sm">
          <DashboardWidgetKpi :config="previewConfig" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { WidgetConfig, KpiWidgetConfig } from '~/types/dashboard'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
}>()

const kpiConfig = computed(() => props.modelValue.config as KpiWidgetConfig)

// Local state mirroring config
const localLabel = ref(kpiConfig.value.label)
const localValue = ref(String(kpiConfig.value.value))
const localPrefix = ref(kpiConfig.value.prefix ?? '')
const localSuffix = ref(kpiConfig.value.suffix ?? '')
const hasTrend = ref(!!kpiConfig.value.trend)
const localTrendDirection = ref<'up' | 'down' | 'neutral'>(kpiConfig.value.trend?.direction ?? 'up')
const localTrendValue = ref(kpiConfig.value.trend?.value ?? 0)
const localTrendPeriod = ref(kpiConfig.value.trend?.period ?? '')
const hasSparkline = ref(!!(kpiConfig.value.sparkline?.length))
const sparklineInput = ref((kpiConfig.value.sparkline ?? []).join(', '))

function buildConfig(): WidgetConfig {
  const parsedValue = isNaN(Number(localValue.value)) ? localValue.value : Number(localValue.value)
  const sparklineNums = sparklineInput.value
    .split(',')
    .map(s => parseFloat(s.trim()))
    .filter(n => !isNaN(n))

  return {
    type: 'kpi',
    config: {
      label: localLabel.value,
      value: parsedValue,
      prefix: localPrefix.value || undefined,
      suffix: localSuffix.value || undefined,
      trend: hasTrend.value ? {
        direction: localTrendDirection.value,
        value: localTrendValue.value,
        period: localTrendPeriod.value || undefined,
      } : undefined,
      sparkline: hasSparkline.value && sparklineNums.length > 0 ? sparklineNums : undefined,
    },
  }
}

// Emit on any local field change
watch(
  [localLabel, localValue, localPrefix, localSuffix, hasTrend, localTrendDirection, localTrendValue, localTrendPeriod, hasSparkline, sparklineInput],
  () => emit('update:modelValue', buildConfig()),
)

const previewConfig = computed(() => (props.modelValue.config as KpiWidgetConfig))

function toggleTrend() {
  hasTrend.value = !hasTrend.value
}

function toggleSparkline() {
  hasSparkline.value = !hasSparkline.value
}
</script>
