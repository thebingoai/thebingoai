<template>
  <div class="space-y-2">
    <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">7-Day Usage</label>
    <div v-if="!dailyTotals.length" class="h-20 flex items-center justify-center text-xs text-gray-400">
      No data yet.
    </div>
    <div v-else class="h-20">
      <canvas ref="canvas" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Chart, BarElement, BarController, CategoryScale, LinearScale, Tooltip } from 'chart.js'

Chart.register(BarElement, BarController, CategoryScale, LinearScale, Tooltip)

const props = defineProps<{
  dailyTotals: { date: string; total: number }[]
}>()

const canvas = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

const buildChart = () => {
  if (!canvas.value || !props.dailyTotals.length) return
  if (chart) chart.destroy()

  const labels = props.dailyTotals.map(d => {
    const dt = new Date(d.date)
    return dt.toLocaleDateString('en', { month: 'short', day: 'numeric' })
  })
  const data = props.dailyTotals.map(d => d.total)

  chart = new Chart(canvas.value, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: 'rgba(249, 115, 22, 0.5)',
        borderColor: 'rgb(249, 115, 22)',
        borderWidth: 1,
        borderRadius: 3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: {
        label: ctx => `${ctx.raw} credits`
      }}},
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 } } },
        y: { grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { font: { size: 10 } }, beginAtZero: true },
      },
    },
  })
}

watch(() => props.dailyTotals, () => buildChart(), { deep: true })
onMounted(() => nextTick(buildChart))
onUnmounted(() => { if (chart) chart.destroy() })
</script>
