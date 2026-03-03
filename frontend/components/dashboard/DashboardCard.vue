<template>
  <div
    class="flex cursor-pointer flex-col rounded-xl border border-gray-100 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
    @click="emit('click')"
  >
    <div class="mb-3 flex items-start justify-between">
      <div class="min-w-0 flex-1">
        <h3 class="truncate text-sm font-medium text-gray-800">{{ dashboard.title }}</h3>
        <p v-if="dashboard.description" class="mt-0.5 line-clamp-2 text-xs text-gray-400">
          {{ dashboard.description }}
        </p>
      </div>
      <span class="ml-3 flex-shrink-0 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
        {{ dashboard.charts.length }} {{ dashboard.charts.length === 1 ? 'chart' : 'charts' }}
      </span>
    </div>

    <div v-if="chartTypeIcons.length > 0" class="flex items-center gap-1.5">
      <component
        :is="icon"
        v-for="(icon, i) in chartTypeIcons"
        :key="i"
        class="h-3.5 w-3.5 text-gray-300"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { BarChart3, LineChart, PieChart, ScatterChart, TrendingUp } from 'lucide-vue-next'
import type { DashboardConfig, ChartType } from '~/types/chart'

const props = defineProps<{
  dashboard: DashboardConfig
}>()

const emit = defineEmits<{
  click: []
}>()

const chartIconMap: Record<ChartType, any> = {
  bar: BarChart3,
  line: LineChart,
  area: TrendingUp,
  pie: PieChart,
  doughnut: PieChart,
  scatter: ScatterChart,
}

const chartTypeIcons = computed(() => {
  const seen = new Set<ChartType>()
  return props.dashboard.charts
    .map(c => c.type)
    .filter(t => {
      if (seen.has(t)) return false
      seen.add(t)
      return true
    })
    .slice(0, 5)
    .map(t => chartIconMap[t])
})
</script>
