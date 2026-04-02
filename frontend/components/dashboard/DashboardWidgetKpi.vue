<template>
  <div class="relative h-full overflow-hidden">
    <!-- Sparkline background (behind content) -->
    <div v-if="config.sparkline && config.sparkline.length > 0"
         class="absolute inset-0 opacity-30 pointer-events-none">
      <canvas ref="sparklineRef" class="w-full h-full" />
    </div>

    <!-- Content overlay -->
    <div class="relative flex h-full flex-col justify-between p-4 z-10">
      <!-- Label -->
      <div class="text-xs font-medium text-gray-400 uppercase tracking-wide">{{ config.label }}</div>

      <!-- Main value -->
      <div class="flex items-baseline gap-1 mt-2">
        <span v-if="config.prefix" class="text-sm font-medium text-gray-500">{{ config.prefix }}</span>
        <span class="text-2xl font-semibold text-gray-900 tabular-nums">{{ formattedValue }}</span>
        <span v-if="config.suffix" class="text-sm font-medium text-gray-500">{{ config.suffix }}</span>
      </div>

      <!-- Trend row -->
      <div v-if="config.trend" class="flex items-center gap-1.5 mt-1">
        <component
          :is="trendIcon"
          class="h-3.5 w-3.5 flex-shrink-0"
          :class="trendColor"
        />
        <span class="text-xs font-medium tabular-nums" :class="trendColor">
          {{ config.trend.value }}%
        </span>
        <span v-if="config.trend.period" class="text-xs text-gray-400">{{ config.trend.period }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { TrendingUp, TrendingDown, Minus } from 'lucide-vue-next'
import type { KpiWidgetConfig } from '~/types/dashboard'
import { Chart } from 'chart.js'

const props = defineProps<{
  config: KpiWidgetConfig
}>()

const sparklineRef = ref<HTMLCanvasElement | null>(null)
let sparklineInstance: Chart | null = null

const formattedValue = computed(() => {
  const v = props.config.value
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') {
    const dp = props.config.decimalPlaces ?? 2
    const round = !!props.config.roundValue
    if (v >= 1_000_000) {
      const m = v / 1_000_000
      return (round ? m.toFixed(dp) : m.toFixed(2)) + 'M'
    }
    if (v >= 1_000) {
      return round
        ? Number(v.toFixed(dp)).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })
        : v.toLocaleString()
    }
    if (round) return v.toFixed(dp)
    return v % 1 !== 0 ? v.toFixed(2) : String(v)
  }
  return String(v)
})

const trendIcon = computed(() => {
  switch (props.config.trend?.direction) {
    case 'up': return TrendingUp
    case 'down': return TrendingDown
    default: return Minus
  }
})

const trendColor = computed(() => {
  switch (props.config.trend?.direction) {
    case 'up': return 'text-emerald-500'
    case 'down': return 'text-rose-500'
    default: return 'text-gray-400'
  }
})

function renderSparkline() {
  sparklineInstance?.destroy()
  sparklineInstance = null

  if (!sparklineRef.value || !props.config.sparkline?.length) return

  const color = props.config.trend?.direction === 'down' ? '#f43f5e' : '#6366f1'

  sparklineInstance = new Chart(sparklineRef.value, {
    type: 'line',
    data: {
      labels: props.config.sparklineLabels ?? props.config.sparkline.map(() => ''),
      datasets: [{
        data: props.config.sparkline,
        borderColor: color,
        backgroundColor: `${color}40`,
        borderWidth: 1.5,
        fill: true,
        tension: 0.4,
        pointRadius: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false }, datalabels: { display: false } },
      scales: {
        x: { display: false },
        y: { display: false },
      },
    },
  })
}

onMounted(() => renderSparkline())

// Re-render sparkline when data changes (e.g. after refresh)
watch(() => props.config.sparkline, () => {
  nextTick(() => renderSparkline())
})

onBeforeUnmount(() => {
  sparklineInstance?.destroy()
})
</script>
