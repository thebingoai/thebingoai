<template>
  <div class="relative flex h-full flex-col overflow-hidden">
    <!-- Edit mode controls overlay -->
    <div
      v-if="editMode"
      class="absolute inset-x-0 top-0 z-10 flex items-center justify-between bg-white/90 px-3 py-1.5 border-b border-gray-100 backdrop-blur-sm"
    >
      <!-- Drag handle -->
      <div class="widget-drag-handle flex cursor-grab items-center gap-1.5 active:cursor-grabbing">
        <GripVertical class="h-3.5 w-3.5 text-gray-300" />
        <span v-if="widget.title" class="text-[11px] font-medium text-gray-500 truncate max-w-[140px]">{{ widget.title }}</span>
        <span v-else class="text-[11px] text-gray-400 capitalize">{{ widget.widget.type }}</span>
      </div>
      <!-- Remove button -->
      <button
        class="flex h-5 w-5 items-center justify-center rounded text-gray-300 hover:bg-rose-50 hover:text-rose-500 transition-colors"
        @click="emit('remove', widget.id)"
      >
        <X class="h-3 w-3" />
      </button>
    </div>

    <!-- Widget body -->
    <div class="min-h-0 flex-1 overflow-hidden" :class="editMode ? 'pt-7' : ''">
      <DashboardWidgetKpi
        v-if="widget.widget.type === 'kpi'"
        :config="widget.widget.config"
      />
      <DashboardWidgetChart
        v-else-if="widget.widget.type === 'chart'"
        :config="widget.widget.config"
      />
      <DashboardWidgetTable
        v-else-if="widget.widget.type === 'table'"
        :config="widget.widget.config"
      />
      <DashboardWidgetText
        v-else-if="widget.widget.type === 'text'"
        :config="widget.widget.config"
      />
      <DashboardWidgetFilter
        v-else-if="widget.widget.type === 'filter'"
        :config="widget.widget.config"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { GripVertical, X } from 'lucide-vue-next'
import type { DashboardWidget } from '~/types/dashboard'

const props = defineProps<{
  widget: DashboardWidget
  editMode: boolean
}>()

const emit = defineEmits<{
  remove: [id: string]
}>()
</script>
