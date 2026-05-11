<template>
  <div class="flex flex-col flex-shrink-0 border-b border-dashed border-gray-200 bg-gray-50/50 px-3 py-2 gap-2 dark:border-neutral-700">
    <!-- Primary row: label + first 3 tags + toggle arrow -->
    <div class="flex items-center gap-2">
      <span class="text-xs font-medium text-gray-600 dark:text-gray-300 shrink-0 whitespace-nowrap">Add widget:</span>
      <div class="flex items-center gap-2">
        <button
          v-for="item in primaryTypes"
          :key="item.type"
          class="flex shrink-0 items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-600 whitespace-nowrap hover:border-gray-300 hover:text-gray-900 transition-colors shadow-sm dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300 dark:hover:border-neutral-500 dark:hover:text-white"
          @click="emit('add-widget', item.type)"
        >
          <component :is="item.icon" class="h-3.5 w-3.5 text-gray-400 dark:text-neutral-400" />
          {{ item.label }}
        </button>
      </div>
      <button
        class="shrink-0 ml-auto text-gray-400 hover:text-gray-600 dark:text-neutral-500 dark:hover:text-neutral-300 transition-colors"
        @click="expanded = !expanded"
      >
        <ChevronDown v-if="!expanded" class="h-4 w-4" />
        <ChevronUp v-else class="h-4 w-4" />
      </button>
    </div>

    <!-- Secondary row: extra tags shown when expanded -->
    <div v-if="expanded" class="flex items-center gap-2 flex-wrap">
      <button
        v-for="item in secondaryTypes"
        :key="item.type"
        class="flex shrink-0 items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-600 whitespace-nowrap hover:border-gray-300 hover:text-gray-900 transition-colors shadow-sm dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300 dark:hover:border-neutral-500 dark:hover:text-white"
        @click="emit('add-widget', item.type)"
      >
        <component :is="item.icon" class="h-3.5 w-3.5 text-gray-400 dark:text-neutral-400" />
        {{ item.label }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { TrendingUp, BarChart3, Table2, FileText, SlidersHorizontal, ChevronDown, ChevronUp } from 'lucide-vue-next'
import type { WidgetType } from '~/types/dashboard'

const emit = defineEmits<{ 'add-widget': [type: WidgetType] }>()

const expanded = ref(false)

const primaryTypes = [
  { type: 'kpi' as WidgetType,    label: 'Score Chart', icon: TrendingUp },
  { type: 'chart' as WidgetType,  label: 'Chart',       icon: BarChart3 },
  { type: 'table' as WidgetType,  label: 'Table',       icon: Table2 },
]

const secondaryTypes = [
  { type: 'text' as WidgetType,   label: 'Text',   icon: FileText },
  { type: 'filter' as WidgetType, label: 'Filter', icon: SlidersHorizontal },
]
</script>
