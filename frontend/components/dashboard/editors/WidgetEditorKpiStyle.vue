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
          @click="editMode && toggle('showTitle')"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localShowTitle ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <template v-if="localShowTitle">
        <div class="space-y-1">
          <label class="text-xs text-gray-700">Title text</label>
          <input
            v-model="localTitle"
            type="text"
            placeholder="Scorecard title…"
            :readonly="!editMode"
            class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
            :class="!editMode ? 'cursor-default bg-gray-50' : ''"
            @input="emitUpdate()"
          />
        </div>

        <div class="space-y-1.5">
          <label class="text-xs text-gray-700">Position</label>
          <div class="flex rounded border border-gray-200 overflow-hidden">
            <button
              v-for="opt in [{ value: 'top', label: 'Top' }, { value: 'bottom', label: 'Bottom' }]"
              :key="opt.value"
              type="button"
              :disabled="!editMode"
              class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="(localTitlePosition ?? 'top') === opt.value
                ? 'bg-indigo-600 text-white'
                : 'bg-white text-gray-500 hover:bg-gray-50'"
              @click="editMode && setTitlePosition(opt.value as 'top' | 'bottom')"
            >{{ opt.label }}</button>
          </div>
        </div>
      </template>
    </div>

    <!-- Primary metric -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Primary Metric</h3>

      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Compact numbers</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localCompactNumbers"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localCompactNumbers ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('compactNumbers')"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localCompactNumbers ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Round value</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localRoundValue"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localRoundValue ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('roundValue')"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localRoundValue ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <div v-if="localRoundValue" class="flex items-center justify-between gap-2">
        <span class="text-xs text-gray-700">Decimal places</span>
        <input
          v-model.number="localDecimalPlaces"
          type="number"
          min="0"
          max="10"
          :disabled="!editMode"
          class="w-16 rounded border border-gray-200 bg-white px-2 py-1 text-xs text-center focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
          @input="emitUpdate()"
        />
      </div>
    </div>

    <!-- Comparison fields -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Comparison Fields</h3>

      <div class="flex items-center justify-between">
        <span class="text-xs text-gray-700">Positive change color</span>
        <ColorPickerPopover
          :model-value="localPositiveColor || undefined"
          :disabled="!editMode"
          @update:model-value="(c) => { localPositiveColor = c ?? ''; emitUpdate() }"
        />
      </div>

      <div class="flex items-center justify-between">
        <span class="text-xs text-gray-700">Negative change color</span>
        <ColorPickerPopover
          :model-value="localNegativeColor || undefined"
          :disabled="!editMode"
          @update:model-value="(c) => { localNegativeColor = c ?? ''; emitUpdate() }"
        />
      </div>

      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Compact numbers</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localCompactComparison"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localCompactComparison ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('compactComparison')"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localCompactComparison ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Show absolute change</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localShowAbsoluteChange"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localShowAbsoluteChange ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('showAbsoluteChange')"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localShowAbsoluteChange ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Hide comparison label</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localHideComparisonLabel"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localHideComparisonLabel ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('hideComparisonLabel')"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localHideComparisonLabel ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <div v-if="!localHideComparisonLabel" class="space-y-1">
        <label class="text-xs text-gray-700">Custom comparison label</label>
        <input
          v-model="localCustomComparisonLabel"
          type="text"
          placeholder="e.g. vs last month"
          :readonly="!editMode"
          class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
          :class="!editMode ? 'cursor-default bg-gray-50' : ''"
          @input="emitUpdate()"
        />
      </div>
    </div>

    <!-- Sparkline -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Sparkline</h3>

      <div class="flex items-center justify-between">
        <span class="text-xs text-gray-700">Color</span>
        <ColorPickerPopover
          :model-value="localSparklineColor || undefined"
          :disabled="!editMode"
          @update:model-value="(c) => { localSparklineColor = c ?? ''; emitUpdate() }"
        />
      </div>

      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Fill</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localSparklineFill"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localSparklineFill ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('sparklineFill')"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localSparklineFill ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Smooth</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localSparklineSmooth"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localSparklineSmooth ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('sparklineSmooth')"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localSparklineSmooth ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <div class="space-y-1.5">
        <label class="text-xs text-gray-700">Missing data</label>
        <div class="flex rounded border border-gray-200 overflow-hidden">
          <button
            v-for="opt in sparklineMissingOptions"
            :key="opt.value"
            type="button"
            :disabled="!editMode"
            class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localSparklineMissingData ?? 'linear') === opt.value
              ? 'bg-indigo-600 text-white'
              : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="editMode && setSparklineMissingData(opt.value as 'linear' | 'breaks' | 'zero')"
          >{{ opt.label }}</button>
        </div>
      </div>
    </div>

    <!-- Progress visual -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Progress Visual</h3>
      <div class="space-y-1.5">
        <label class="text-xs text-gray-700">Style</label>
        <div class="flex rounded border border-gray-200 overflow-hidden">
          <button
            v-for="opt in progressVisualOptions"
            :key="opt.value"
            type="button"
            :disabled="!editMode"
            class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localProgressVisual ?? 'bar') === opt.value
              ? 'bg-indigo-600 text-white'
              : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="editMode && setProgressVisual(opt.value as 'bar' | 'circle' | 'none')"
          >{{ opt.label }}</button>
        </div>
      </div>
    </div>

    <!-- Missing data -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Missing Data</h3>
      <div class="flex rounded border border-gray-200 overflow-hidden">
        <button
          v-for="opt in missingDataOptions"
          :key="opt.value"
          type="button"
          :disabled="!editMode"
          class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="(localMissingData ?? 'dash') === opt.value
            ? 'bg-indigo-600 text-white'
            : 'bg-white text-gray-500 hover:bg-gray-50'"
          @click="editMode && setMissingData(opt.value as 'noData' | 'zero' | 'dash' | 'null' | 'blank')"
        >{{ opt.label }}</button>
      </div>
    </div>

    <!-- Labels -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Labels</h3>

      <div class="flex items-center justify-between gap-2">
        <span class="text-xs text-gray-700">Font</span>
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
            :class="(localFontSize ?? 'md') === opt.value
              ? 'bg-indigo-600 text-white'
              : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="editMode && setFontSize(opt.value as 'xs' | 'sm' | 'md' | 'lg' | 'xl')"
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

      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Hide field name</span>
        <button
          type="button"
          role="switch"
          :aria-checked="localHideFieldName"
          :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localHideFieldName ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('hideFieldName')"
        >
          <span
            class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localHideFieldName ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
          />
        </button>
      </div>

      <div class="space-y-1.5">
        <label class="text-xs text-gray-700">Alignment</label>
        <div class="flex rounded border border-gray-200 overflow-hidden">
          <button
            v-for="opt in alignOptions"
            :key="opt.value"
            type="button"
            :disabled="!editMode"
            class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localAlignment ?? 'left') === opt.value
              ? 'bg-indigo-600 text-white'
              : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="editMode && setAlignment(opt.value as 'left' | 'center' | 'right')"
          >{{ opt.label }}</button>
        </div>
      </div>
    </div>

    <!-- Background & Border -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Background &amp; Border</h3>

      <div class="flex items-center justify-between">
        <span class="text-xs text-gray-700">Background</span>
        <ColorPickerPopover
          :model-value="localBackgroundColor || undefined"
          :disabled="!editMode"
          @update:model-value="(c) => { localBackgroundColor = c ?? ''; emitUpdate() }"
        />
      </div>

      <div class="flex items-center justify-between gap-2">
        <span class="text-xs text-gray-700">Opacity</span>
        <div class="flex items-center gap-2 flex-1 max-w-[140px]">
          <input
            v-model.number="localOpacity"
            type="range"
            min="0"
            max="100"
            :disabled="!editMode"
            class="flex-1 disabled:opacity-40"
            @input="emitUpdate()"
          />
          <span class="text-[11px] text-gray-500 tabular-nums w-8 text-right">{{ localOpacity }}%</span>
        </div>
      </div>

      <div class="flex items-center justify-between">
        <span class="text-xs text-gray-700">Border color</span>
        <ColorPickerPopover
          :model-value="localBorderColor || undefined"
          :disabled="!editMode"
          @update:model-value="(c) => { localBorderColor = c ?? ''; emitUpdate() }"
        />
      </div>

      <div class="space-y-1.5">
        <label class="text-xs text-gray-700">Border style</label>
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
            @click="editMode && setBorderStyle(opt.value as 'solid' | 'dashed' | 'dotted' | 'none')"
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

  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { WidgetConfig, KpiWidgetConfig, KpiComparisonConfig } from '~/types/dashboard'
import ColorPickerPopover from './ColorPickerPopover.vue'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
}>()

const cfg = () => props.modelValue.config as KpiWidgetConfig
const comp = (): Partial<KpiComparisonConfig> => cfg().comparison ?? {}

// Title
const localShowTitle = ref(!!cfg().showTitle)
const localTitle = ref(cfg().title ?? '')
const localTitlePosition = ref<'top' | 'bottom'>(cfg().titlePosition ?? 'top')

// Primary metric
const localCompactNumbers = ref(!!cfg().compactNumbers)
const localRoundValue = ref(!!cfg().roundValue)
const localDecimalPlaces = ref(cfg().decimalPlaces ?? 2)

// Comparison fields
const localPositiveColor = ref(comp().positiveChangeColor ?? '')
const localNegativeColor = ref(comp().negativeChangeColor ?? '')
const localCompactComparison = ref(!!comp().compactNumbers)
const localShowAbsoluteChange = ref(!!comp().showAbsoluteChange)
const localHideComparisonLabel = ref(!!comp().hideComparisonLabel)
const localCustomComparisonLabel = ref(comp().comparisonLabel ?? '')

// Sparkline
const localSparklineColor = ref(cfg().sparklineColor ?? '')
const localSparklineFill = ref(cfg().sparklineFill !== false) // default true
const localSparklineSmooth = ref(cfg().sparklineSmooth !== false) // default true
const localSparklineMissingData = ref<'linear' | 'breaks' | 'zero'>(cfg().sparklineMissingData ?? 'linear')

// Progress visual
const localProgressVisual = ref<'bar' | 'circle' | 'none'>(cfg().progressVisual ?? 'bar')

// Missing data
const localMissingData = ref<'noData' | 'zero' | 'dash' | 'null' | 'blank'>(cfg().missingDataDisplay ?? 'dash')

// Labels
const localFontFamily = ref<'system' | 'sans' | 'serif' | 'mono'>(cfg().fontFamily ?? 'system')
const localFontSize = ref<'xs' | 'sm' | 'md' | 'lg' | 'xl'>(cfg().fontSize ?? 'md')
const localFontColor = ref(cfg().fontColor ?? '')
const localHideFieldName = ref(!!cfg().hideFieldName)
const localAlignment = ref<'left' | 'center' | 'right'>(cfg().alignment ?? 'left')

// Background & border
const localBackgroundColor = ref(cfg().backgroundColor ?? '')
const localOpacity = ref(Math.round((cfg().opacity ?? 1) * 100))
const localBorderColor = ref(cfg().borderColor ?? '')
const localBorderStyle = ref<'solid' | 'dashed' | 'dotted' | 'none'>(cfg().borderStyle ?? 'solid')
const localBorderWidth = ref(cfg().borderWidth ?? 0)
const localBorderRadius = ref(cfg().borderRadius ?? 0)

// Option lists
const sparklineMissingOptions = [
  { value: 'linear', label: 'Linear' },
  { value: 'breaks', label: 'Breaks' },
  { value: 'zero', label: 'Zero' },
]
const progressVisualOptions = [
  { value: 'bar', label: 'Bar' },
  { value: 'circle', label: 'Circle' },
  { value: 'none', label: 'None' },
]
const missingDataOptions = [
  { value: 'dash', label: '—' },
  { value: 'noData', label: 'No data' },
  { value: 'zero', label: '0' },
  { value: 'null', label: 'null' },
  { value: 'blank', label: 'Blank' },
]
const fontSizeOptions = [
  { value: 'xs', label: 'XS' },
  { value: 'sm', label: 'S' },
  { value: 'md', label: 'M' },
  { value: 'lg', label: 'L' },
  { value: 'xl', label: 'XL' },
]
const alignOptions = [
  { value: 'left', label: 'Left' },
  { value: 'center', label: 'Center' },
  { value: 'right', label: 'Right' },
]
const borderStyleOptions = [
  { value: 'solid', label: 'Solid' },
  { value: 'dashed', label: 'Dashed' },
  { value: 'dotted', label: 'Dotted' },
  { value: 'none', label: 'None' },
]

// Toggle helpers for boolean fields
const boolFields: Record<string, () => boolean> = {
  showTitle: () => (localShowTitle.value = !localShowTitle.value),
  compactNumbers: () => (localCompactNumbers.value = !localCompactNumbers.value),
  roundValue: () => (localRoundValue.value = !localRoundValue.value),
  compactComparison: () => (localCompactComparison.value = !localCompactComparison.value),
  showAbsoluteChange: () => (localShowAbsoluteChange.value = !localShowAbsoluteChange.value),
  hideComparisonLabel: () => (localHideComparisonLabel.value = !localHideComparisonLabel.value),
  sparklineFill: () => (localSparklineFill.value = !localSparklineFill.value),
  sparklineSmooth: () => (localSparklineSmooth.value = !localSparklineSmooth.value),
  hideFieldName: () => (localHideFieldName.value = !localHideFieldName.value),
}

function toggle(key: string) {
  boolFields[key]?.()
  emitUpdate()
}

function setTitlePosition(v: 'top' | 'bottom') { localTitlePosition.value = v; emitUpdate() }
function setSparklineMissingData(v: 'linear' | 'breaks' | 'zero') { localSparklineMissingData.value = v; emitUpdate() }
function setProgressVisual(v: 'bar' | 'circle' | 'none') { localProgressVisual.value = v; emitUpdate() }
function setMissingData(v: 'noData' | 'zero' | 'dash' | 'null' | 'blank') { localMissingData.value = v; emitUpdate() }
function setFontSize(v: 'xs' | 'sm' | 'md' | 'lg' | 'xl') { localFontSize.value = v; emitUpdate() }
function setAlignment(v: 'left' | 'center' | 'right') { localAlignment.value = v; emitUpdate() }
function setBorderStyle(v: 'solid' | 'dashed' | 'dotted' | 'none') { localBorderStyle.value = v; emitUpdate() }

function emitUpdate() {
  const existing = cfg()
  emit('update:modelValue', {
    type: 'kpi',
    config: {
      ...existing,
      // title
      title: localTitle.value || undefined,
      showTitle: localShowTitle.value || undefined,
      titlePosition: localTitlePosition.value !== 'top' ? localTitlePosition.value : undefined,
      // primary metric
      compactNumbers: localCompactNumbers.value || undefined,
      roundValue: localRoundValue.value || undefined,
      decimalPlaces: localRoundValue.value ? localDecimalPlaces.value : undefined,
      // comparison style (merged into existing comparison object)
      comparison: existing.comparison
        ? {
            ...existing.comparison,
            positiveChangeColor: localPositiveColor.value || undefined,
            negativeChangeColor: localNegativeColor.value || undefined,
            compactNumbers: localCompactComparison.value || undefined,
            showAbsoluteChange: localShowAbsoluteChange.value || undefined,
            hideComparisonLabel: localHideComparisonLabel.value || undefined,
            comparisonLabel: localHideComparisonLabel.value ? undefined : (localCustomComparisonLabel.value || existing.comparison?.comparisonLabel),
          }
        : {
            type: 'none' as const,
            positiveChangeColor: localPositiveColor.value || undefined,
            negativeChangeColor: localNegativeColor.value || undefined,
            compactNumbers: localCompactComparison.value || undefined,
            showAbsoluteChange: localShowAbsoluteChange.value || undefined,
            hideComparisonLabel: localHideComparisonLabel.value || undefined,
            comparisonLabel: localHideComparisonLabel.value ? undefined : (localCustomComparisonLabel.value || undefined),
          },
      // sparkline appearance
      sparklineColor: localSparklineColor.value || undefined,
      sparklineFill: localSparklineFill.value ? undefined : false, // default is true, only persist when off
      sparklineSmooth: localSparklineSmooth.value ? undefined : false,
      sparklineMissingData: localSparklineMissingData.value !== 'linear' ? localSparklineMissingData.value : undefined,
      // progress visual
      progressVisual: localProgressVisual.value !== 'bar' ? localProgressVisual.value : undefined,
      // missing data
      missingDataDisplay: localMissingData.value !== 'dash' ? localMissingData.value : undefined,
      // labels
      fontFamily: localFontFamily.value !== 'system' ? localFontFamily.value : undefined,
      fontSize: localFontSize.value !== 'md' ? localFontSize.value : undefined,
      fontColor: localFontColor.value || undefined,
      hideFieldName: localHideFieldName.value || undefined,
      alignment: localAlignment.value !== 'left' ? localAlignment.value : undefined,
      // background & border
      backgroundColor: localBackgroundColor.value || undefined,
      opacity: localOpacity.value < 100 ? localOpacity.value / 100 : undefined,
      borderColor: localBorderColor.value || undefined,
      borderStyle: localBorderStyle.value !== 'solid' ? localBorderStyle.value : undefined,
      borderWidth: localBorderWidth.value > 0 ? localBorderWidth.value : undefined,
      borderRadius: localBorderRadius.value > 0 ? localBorderRadius.value : undefined,
    },
  })
}
</script>
