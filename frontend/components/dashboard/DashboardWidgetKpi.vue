<template>
  <div class="flex h-full flex-col justify-between p-4">
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

    <!-- Sparkline -->
    <div v-if="config.sparkline && config.sparkline.length > 0" class="mt-3 h-8">
      <canvas ref="sparklineRef" class="w-full h-full" />
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
    if (v >= 1_000_000) return (v / 1_000_000).toFixed(2) + 'M'
    if (v >= 1_000) return v.toLocaleString()
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

onMounted(() => {
  if (!sparklineRef.value || !props.config.sparkline?.length) return

  const color = props.config.trend?.direction === 'down' ? '#f43f5e' : '#6366f1'

  sparklineInstance = new Chart(sparklineRef.value, {
    type: 'line',
    data: {
      labels: props.config.sparkline.map(() => ''),
      datasets: [{
        data: props.config.sparkline,
        borderColor: color,
        backgroundColor: `${color}22`,
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
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: {
        x: { display: false },
        y: { display: false },
      },
    },
  })
})

onBeforeUnmount(() => {
  sparklineInstance?.destroy()
})
</script>
