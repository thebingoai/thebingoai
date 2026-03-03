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
        {{ dashboard.widgetCount }} {{ dashboard.widgetCount === 1 ? 'widget' : 'widgets' }}
      </span>
    </div>

    <div v-if="widgetTypeIcons.length > 0" class="flex items-center gap-1.5">
      <component
        :is="icon"
        v-for="(icon, i) in widgetTypeIcons"
        :key="i"
        class="h-3.5 w-3.5 text-gray-300"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { BarChart3, LineChart, TrendingUp, Table2, FileText, SlidersHorizontal } from 'lucide-vue-next'
import type { DashboardListItem, WidgetType } from '~/types/dashboard'

const props = defineProps<{
  dashboard: DashboardListItem
}>()

const emit = defineEmits<{
  click: []
}>()

const widgetIconMap: Record<WidgetType, any> = {
  kpi: TrendingUp,
  chart: BarChart3,
  table: Table2,
  text: FileText,
  filter: SlidersHorizontal,
}

const widgetTypeIcons = computed(() =>
  props.dashboard.widgetTypes.slice(0, 5).map(t => widgetIconMap[t]),
)
</script>
