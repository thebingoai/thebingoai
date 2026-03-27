<template>
  <div
    class="flex cursor-pointer flex-col overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm transition-shadow hover:shadow-md"
    @click="emit('click')"
  >
    <DashboardPreviewGrid :widgets="dashboard.widgets" />

    <div class="border-t border-gray-100 p-4">
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

      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3 min-w-0">
          <div v-if="widgetTypeIcons.length > 0" class="flex items-center gap-1.5">
            <component
              :is="icon"
              v-for="(icon, i) in widgetTypeIcons"
              :key="i"
              class="h-3.5 w-3.5 text-gray-300"
            />
          </div>
          <span v-if="formattedDate" class="truncate text-[10px] text-gray-300">
            {{ formattedDate }}
          </span>
        </div>
        <button
          class="flex h-6 w-6 items-center justify-center rounded-lg text-gray-300 hover:bg-indigo-50 hover:text-indigo-500 transition-colors"
          title="Duplicate dashboard"
          @click.stop="emit('duplicate')"
        >
          <Copy class="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { BarChart3, LineChart, TrendingUp, Table2, FileText, SlidersHorizontal, Copy } from 'lucide-vue-next'
import type { DashboardListItem, WidgetType } from '~/types/dashboard'

const props = defineProps<{
  dashboard: DashboardListItem
}>()

const emit = defineEmits<{
  click: []
  duplicate: []
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

const formattedDate = computed(() => {
  if (!props.dashboard.createdAt) return ''
  const date = new Date(props.dashboard.createdAt)
  if (isNaN(date.getTime())) return ''
  const now = new Date()
  const sameYear = date.getFullYear() === now.getFullYear()
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    ...(sameYear ? {} : { year: 'numeric' }),
  })
})
</script>
