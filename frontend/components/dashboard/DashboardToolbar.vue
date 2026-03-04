<template>
  <div class="flex flex-shrink-0 items-center gap-2 border-b border-dashed border-gray-200 bg-gray-50/50 px-6 py-2">
    <span class="text-xs font-medium text-gray-400 mr-1">Add widget:</span>
    <button
      v-for="item in widgetTypes"
      :key="item.type"
      class="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-600 hover:border-gray-300 hover:text-gray-900 transition-colors shadow-sm"
      @click="emit('add-widget', item.type)"
    >
      <component :is="item.icon" class="h-3.5 w-3.5 text-gray-400" />
      {{ item.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { TrendingUp, BarChart3, Table2, FileText, SlidersHorizontal } from 'lucide-vue-next'
import type { WidgetType } from '~/types/dashboard'

const emit = defineEmits<{
  'add-widget': [type: WidgetType]
}>()

const widgetTypes = [
  { type: 'kpi' as WidgetType,    label: 'Score Chart',    icon: TrendingUp },
  { type: 'chart' as WidgetType,  label: 'Chart',  icon: BarChart3 },
  { type: 'table' as WidgetType,  label: 'Table',  icon: Table2 },
  { type: 'text' as WidgetType,   label: 'Text',   icon: FileText },
  { type: 'filter' as WidgetType, label: 'Filter', icon: SlidersHorizontal },
]
</script>
