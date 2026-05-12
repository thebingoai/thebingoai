<template>
  <div
    class="relative h-full overflow-hidden flex flex-col"
    :style="containerStyle"
  >
    <!-- Optional chart title (distinct from metric label) -->
    <div
      v-if="config.showTitle && config.title && config.titlePosition !== 'bottom'"
      class="flex-shrink-0 px-4 pt-3 pb-0"
    >
      <span class="widget-label">{{ config.title }}</span>
    </div>

    <!-- Sparkline background (behind content, hidden when showAsProgress) -->
    <div
      v-if="config.sparkline?.length && !showProgress"
      class="absolute inset-0 pointer-events-none"
      style="opacity: 0.15;"
    >
      <canvas ref="sparklineRef" class="w-full h-full" />
    </div>

    <!-- Content overlay -->
    <div
      class="relative flex flex-col justify-between px-4 py-3 z-10 flex-1 min-h-0 min-w-0"
      :class="alignClass"
    >
      <!-- Metric label -->
      <div
        v-if="!config.hideFieldName"
        class="widget-label truncate max-w-full"
        :style="labelStyle"
        :title="config.label"
      >{{ config.label }}</div>

      <!-- Main value -->
      <div class="flex items-baseline gap-1 mt-2 max-w-full overflow-hidden" :class="justifyClass">
        <span v-if="config.prefix" class="text-sm font-medium text-[var(--ink-3)] flex-shrink-0">{{ config.prefix }}</span>
        <span
          class="kpi-value truncate"
          :class="[kpiValueClass, valueSizeClass]"
          :style="valueColorStyle"
          :title="String(formattedValue)"
        >{{ formattedValue }}</span>
        <span v-if="config.suffix" class="text-sm font-medium text-[var(--ink-3)] flex-shrink-0">{{ config.suffix }}</span>
      </div>

      <!-- Progress visual (bar or circle) — shown when showAsProgress is on -->
      <template v-if="showProgress && progressPct !== null">
        <!-- Bar -->
        <div v-if="progressVisual !== 'circle' && progressVisual !== 'none'" class="mt-3 space-y-1">
          <div class="h-2 rounded-full overflow-hidden bg-gray-100 dark:bg-neutral-700">
            <div
              class="h-full rounded-full transition-all duration-500"
              :style="{ width: (progressPct * 100).toFixed(1) + '%', background: progressColor }"
            />
          </div>
          <div v-if="!config.comparison?.hideComparisonLabel" class="text-[11px] text-[var(--ink-3)] tabular-nums">
            {{ (progressPct * 100).toFixed(1) }}% {{ comparisonLabel }}
          </div>
        </div>

        <!-- Circle -->
        <div v-else-if="progressVisual === 'circle'" class="mt-3 flex items-center gap-3" :class="justifyClass">
          <svg width="48" height="48" viewBox="0 0 48 48" class="flex-shrink-0">
            <circle cx="24" cy="24" r="20" fill="none" stroke="currentColor" stroke-width="4" class="text-gray-100 dark:text-neutral-700" />
            <circle
              cx="24" cy="24" r="20" fill="none"
              :stroke="progressColor"
              stroke-width="4"
              stroke-linecap="round"
              stroke-dasharray="125.66"
              :stroke-dashoffset="125.66 * (1 - Math.min(1, Math.max(0, progressPct)))"
              transform="rotate(-90 24 24)"
            />
            <text x="24" y="28" text-anchor="middle" font-size="10" :fill="progressColor" font-weight="600">
              {{ (progressPct * 100).toFixed(0) }}%
            </text>
          </svg>
          <span v-if="!config.comparison?.hideComparisonLabel" class="text-[11px] text-[var(--ink-3)]">{{ comparisonLabel }}</span>
        </div>
      </template>

      <!-- Comparison / trend row (shown when NOT showAsProgress) -->
      <div
        v-else-if="comparisonDisplay && !showProgress"
        class="flex items-center gap-1.5 mt-1"
        :class="justifyClass"
      >
        <component
          :is="comparisonDisplay.icon"
          class="h-3.5 w-3.5 flex-shrink-0"
          :style="{ color: comparisonDisplay.color }"
        />
        <span
          class="text-xs font-medium tabular-nums font-mono"
          :style="{ color: comparisonDisplay.color }"
        >{{ comparisonDisplay.delta }}</span>
        <span v-if="!config.comparison?.hideComparisonLabel" class="text-xs text-[var(--ink-3)]">
          {{ comparisonDisplay.label }}
        </span>
      </div>
    </div>

    <!-- Optional chart title at bottom -->
    <div
      v-if="config.showTitle && config.title && config.titlePosition === 'bottom'"
      class="flex-shrink-0 px-4 pb-3 pt-0"
    >
      <span class="widget-label">{{ config.title }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { TrendingUp, TrendingDown, Minus } from 'lucide-vue-next'
import type { KpiWidgetConfig } from '~/types/dashboard'
import { Chart } from 'chart.js'

const POSITIVE_COLOR_DEFAULT = 'var(--d-teal)'
const NEGATIVE_COLOR_DEFAULT = 'var(--d-ember)'

const props = defineProps<{
  config: KpiWidgetConfig
}>()

const sparklineRef = ref<HTMLCanvasElement | null>(null)
let sparklineInstance: Chart | null = null

// ——————————————————————————————————————————
// Derived comparison (back-compat: prefer `comparison`, fall back to `trend`)
// ——————————————————————————————————————————
const effectiveComparison = computed(() => {
  if (props.config.comparison && props.config.comparison.type !== 'none') {
    return props.config.comparison
  }
  if (props.config.trend) {
    return {
      type: 'period' as const,
      comparisonLabel: props.config.trend.period,
      positiveChangeColor: undefined,
      negativeChangeColor: undefined,
    }
  }
  return null
})

const showProgress = computed(() => {
  const c = props.config.comparison
  return !!(c && (c.type === 'value' || c.type === 'metric') && c.showAsProgress)
})

const progressVisual = computed(() => props.config.progressVisual ?? 'bar')

// ——————————————————————————————————————————
// Primary value formatting
// ——————————————————————————————————————————
function missingValue(): string {
  switch (props.config.missingDataDisplay) {
    case 'noData': return 'No data'
    case 'zero': return '0'
    case 'null': return 'null'
    case 'blank': return ''
    default: return '—'
  }
}

function formatCompact(num: number): string {
  const abs = Math.abs(num)
  if (abs >= 1e9) return (num / 1e9).toFixed(1).replace(/\.0$/, '') + 'B'
  if (abs >= 1e6) return (num / 1e6).toFixed(1).replace(/\.0$/, '') + 'M'
  if (abs >= 1e3) return (num / 1e3).toFixed(1).replace(/\.0$/, '') + 'K'
  return num.toLocaleString()
}

const formattedValue = computed(() => {
  const v = props.config.value
  if (v === null || v === undefined) return missingValue()
  if (typeof v === 'number') {
    if (props.config.compactNumbers) return formatCompact(v)
    const dp = props.config.decimalPlaces ?? 2
    const round = !!props.config.roundValue
    if (round) return v.toFixed(dp).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
    if (v % 1 !== 0) return v.toFixed(2)
    return v.toLocaleString()
  }
  return String(v)
})

// ——————————————————————————————————————————
// Comparison display (delta text + icon + color + label)
// ——————————————————————————————————————————
const comparisonLabel = computed(() => {
  const c = props.config.comparison
  if (c?.comparisonLabel) return c.comparisonLabel
  if (props.config.trend?.period) return props.config.trend.period
  return ''
})

const comparisonDisplay = computed(() => {
  const ec = effectiveComparison.value
  if (!ec) return null

  const positiveColor = ec.positiveChangeColor || POSITIVE_COLOR_DEFAULT
  const negativeColor = ec.negativeChangeColor || NEGATIVE_COLOR_DEFAULT
  const showAbsolute = !!props.config.comparison?.showAbsoluteChange

  if (ec.type === 'period') {
    // Period comparison — uses pre-computed trend data from the backend
    const t = props.config.trend
    if (!t) return null
    const pct = t.value
    const icon = t.direction === 'up' ? TrendingUp : t.direction === 'down' ? TrendingDown : Minus
    const color = t.direction === 'up' ? positiveColor : t.direction === 'down' ? negativeColor : 'var(--ink-3)'
    const delta = `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`
    return { icon, color, delta, label: comparisonLabel.value }
  }

  if (ec.type === 'value' || ec.type === 'metric') {
    const primaryNum = typeof props.config.value === 'number' ? props.config.value : Number(props.config.value)
    if (!isFinite(primaryNum)) return null
    const target = ec.type === 'value' ? (ec.targetValue ?? null) : null
    if (target === null) return null

    const diff = primaryNum - target
    const pct = target !== 0 ? (diff / Math.abs(target)) * 100 : (diff > 0 ? 100 : diff < 0 ? -100 : 0)
    const isPositive = diff >= 0

    const icon = isPositive ? TrendingUp : TrendingDown
    const color = isPositive ? positiveColor : negativeColor

    let delta: string
    if (showAbsolute) {
      const fmt = (props.config.comparison?.compactNumbers) ? formatCompact(Math.abs(diff)) : Math.abs(diff).toLocaleString()
      delta = `${diff >= 0 ? '+' : '-'}${fmt}`
    } else {
      delta = `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`
    }
    return { icon, color, delta, label: comparisonLabel.value }
  }

  return null
})

// ——————————————————————————————————————————
// Progress calculation
// ——————————————————————————————————————————
const progressPct = computed(() => {
  if (!showProgress.value) return null
  const c = props.config.comparison!
  const primary = typeof props.config.value === 'number' ? props.config.value : Number(props.config.value)
  if (!isFinite(primary)) return null
  const target = c.type === 'value' ? (c.targetValue ?? null) : null
  if (target === null) return null
  const start = c.startingValue ?? 0
  const range = target - start
  if (range === 0) return 0
  return Math.min(1, Math.max(0, (primary - start) / range))
})

const progressColor = computed(() => {
  const pct = progressPct.value ?? 0
  const c = props.config.comparison
  if (pct >= 1) return c?.positiveChangeColor || POSITIVE_COLOR_DEFAULT
  if (pct < 0.3) return c?.negativeChangeColor || NEGATIVE_COLOR_DEFAULT
  return 'var(--d-amber, #f59e0b)'
})

// ——————————————————————————————————————————
// Styling computeds
// ——————————————————————————————————————————
function applyAlphaToColor(color: string, alpha: number): string {
  const a = Math.max(0, Math.min(1, alpha))
  const hex = color.trim()
  // #RGB or #RRGGBB → rgba()
  const m3 = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/i.exec(hex)
  if (m3) {
    const r = parseInt(m3[1] + m3[1], 16)
    const g = parseInt(m3[2] + m3[2], 16)
    const b = parseInt(m3[3] + m3[3], 16)
    return `rgba(${r}, ${g}, ${b}, ${a})`
  }
  const m6 = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex)
  if (m6) {
    return `rgba(${parseInt(m6[1], 16)}, ${parseInt(m6[2], 16)}, ${parseInt(m6[3], 16)}, ${a})`
  }
  // rgb(r, g, b) → rgba()
  const mRgb = /^rgb\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)$/i.exec(hex)
  if (mRgb) {
    return `rgba(${mRgb[1]}, ${mRgb[2]}, ${mRgb[3]}, ${a})`
  }
  // rgba(...) — replace alpha
  const mRgba = /^rgba\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*[0-9.]+\s*\)$/i.exec(hex)
  if (mRgba) {
    return `rgba(${mRgba[1]}, ${mRgba[2]}, ${mRgba[3]}, ${a})`
  }
  // Unknown format (named color, var()…) — return as-is; alpha can't be inlined
  return color
}

const containerStyle = computed(() => {
  const style: Record<string, string> = {}
  const bg = props.config.backgroundColor
  const opacity = props.config.opacity
  if (bg) {
    if (opacity !== undefined && opacity < 1) {
      style.background = applyAlphaToColor(bg, opacity)
    } else {
      style.background = bg
    }
  }
  if (props.config.borderWidth && props.config.borderWidth > 0) {
    const color = props.config.borderColor ?? '#e5e7eb'
    const bStyle = props.config.borderStyle ?? 'solid'
    style.border = `${props.config.borderWidth}px ${bStyle} ${color}`
  }
  if (props.config.borderRadius && props.config.borderRadius > 0) {
    style.borderRadius = `${props.config.borderRadius}px`
  }
  if (props.config.fontFamily) {
    const map: Record<string, string> = { sans: 'sans-serif', serif: 'serif', mono: 'monospace' }
    if (map[props.config.fontFamily]) style.fontFamily = map[props.config.fontFamily]
  }
  return style
})

const labelStyle = computed(() => {
  const s: Record<string, string> = {}
  if (props.config.fontColor) s.color = props.config.fontColor
  return s
})

const valueColorStyle = computed(() => {
  if (props.config.fontColor) return { color: props.config.fontColor }
  return {}
})

const alignClass = computed(() => {
  switch (props.config.alignment) {
    case 'center': return 'items-center text-center'
    case 'right': return 'items-end text-right'
    default: return 'items-start text-left'
  }
})

const justifyClass = computed(() => {
  switch (props.config.alignment) {
    case 'center': return 'justify-center'
    case 'right': return 'justify-end'
    default: return 'justify-start'
  }
})

const valueSizeClass = computed(() => {
  switch (props.config.fontSize) {
    case 'xs': return 'kpi-value-xs'
    case 'sm': return 'kpi-value-sm'
    case 'lg': return 'kpi-value-lg'
    case 'xl': return 'kpi-value-xl'
    default: return '' // 'md' is the base .kpi-value size
  }
})

// Color applied to main value only when trend/comparison is set (legacy behavior)
const kpiValueClass = computed(() => {
  const t = props.config.trend
  if (!t || props.config.fontColor) return ''
  if (t.direction === 'down') return 'delta-bad'
  if (t.direction === 'up') return 'delta-good'
  return ''
})

// ——————————————————————————————————————————
// Sparkline rendering
// ——————————————————————————————————————————
function resolveSparklineColor(): string {
  if (props.config.sparklineColor) return props.config.sparklineColor
  const t = props.config.trend
  if (t?.direction === 'down') return 'var(--d-ember)'
  return 'var(--d-teal)'
}

function renderSparkline() {
  sparklineInstance?.destroy()
  sparklineInstance = null
  if (!sparklineRef.value || !props.config.sparkline?.length || showProgress.value) return

  const color = resolveSparklineColor()
  const fill = props.config.sparklineFill !== false
  const smooth = props.config.sparklineSmooth !== false
  const missingData = props.config.sparklineMissingData ?? 'linear'

  let spanGaps: boolean | number = missingData === 'linear' || missingData === 'zero'
  if (missingData === 'zero') {
    // replace nulls with 0 before passing to Chart.js
  }

  sparklineInstance = new Chart(sparklineRef.value, {
    type: 'line',
    data: {
      labels: props.config.sparklineLabels ?? props.config.sparkline.map(() => ''),
      datasets: [{
        data: missingData === 'zero'
          ? props.config.sparkline.map(v => v ?? 0)
          : props.config.sparkline,
        borderColor: color,
        backgroundColor: fill ? `${color}40` : 'transparent',
        borderWidth: 1.5,
        fill,
        tension: smooth ? 0.4 : 0,
        pointRadius: 0,
        spanGaps: missingData !== 'breaks',
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { display: false },
        tooltip: { enabled: false },
        datalabels: { display: false },
      },
      scales: { x: { display: false }, y: { display: false } },
    },
  })
}

onMounted(() => renderSparkline())

watch(
  () => [props.config.sparkline, props.config.sparklineColor, props.config.sparklineFill, props.config.sparklineSmooth, props.config.sparklineMissingData] as const,
  () => nextTick(() => renderSparkline()),
)

onBeforeUnmount(() => sparklineInstance?.destroy())
</script>

<style scoped>
.kpi-value {
  font-family: var(--font-display);
  font-style: normal;
  font-weight: 500;
  font-size: 36px;
  font-optical-sizing: auto;
  font-variation-settings: 'opsz' 72;
  line-height: 1;
  letter-spacing: -0.5px;
  color: var(--ink-0);
}
.kpi-value-xs { font-size: 20px; }
.kpi-value-sm { font-size: 28px; }
.kpi-value-lg { font-size: 44px; }
.kpi-value-xl { font-size: 56px; }
.kpi-value.delta-bad  { color: var(--d-ember); }
.kpi-value.delta-good { color: var(--d-teal); }
</style>
