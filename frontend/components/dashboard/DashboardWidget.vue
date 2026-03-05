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
        <span v-else class="text-[11px] text-gray-400">{{ widgetDisplayName }}</span>
      </div>
      <!-- Edit controls -->
      <div class="flex items-center gap-1">
        <!-- SQL editor button — shown when widget has a data source -->
        <button
          v-if="hasDataSource"
          class="flex h-5 w-5 items-center justify-center rounded text-gray-300 hover:bg-indigo-50 hover:text-indigo-500 transition-colors"
          title="View SQL query"
          @click="emit('open-sql-editor', widget.id)"
        >
          <Code class="h-3 w-3" />
        </button>
        <!-- Edit config button -->
        <button
          class="flex h-5 w-5 items-center justify-center rounded text-gray-300 hover:bg-indigo-50 hover:text-indigo-500 transition-colors"
          title="Edit widget config"
          @click="emit('edit-config', widget.id)"
        >
          <Settings class="h-3 w-3" />
        </button>
        <!-- Remove button -->
        <button
          class="flex h-5 w-5 items-center justify-center rounded text-gray-300 hover:bg-rose-50 hover:text-rose-500 transition-colors"
          @click="emit('remove', widget.id)"
        >
          <X class="h-3 w-3" />
        </button>
      </div>
    </div>

    <!-- View mode action bar — only for SQL-backed widgets outside edit mode -->
    <div
      v-if="!editMode && hasDataSource"
      class="absolute inset-x-0 top-0 z-10 flex items-center justify-between px-3 py-1 opacity-0 hover:opacity-100 transition-opacity bg-white/80 backdrop-blur-sm border-b border-gray-100"
    >
      <span v-if="lastRefreshedAt" class="text-[10px] text-gray-400">
        Updated {{ formatRelativeTime(lastRefreshedAt) }}
      </span>
      <span v-else class="text-[10px] text-gray-400">Live data</span>
      <div class="flex items-center gap-1">
        <button
          class="flex h-5 w-5 items-center justify-center rounded text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
          title="View SQL"
          @click="emit('open-sql-editor', widget.id)"
        >
          <Code class="h-3 w-3" />
        </button>
        <button
          class="flex h-5 w-5 items-center justify-center rounded text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          :disabled="loading"
          title="Refresh data"
          @click="refresh()"
        >
          <RefreshCw class="h-3 w-3" :class="{ 'animate-spin': loading }" />
        </button>
      </div>
    </div>

    <!-- Widget body -->
    <div
      class="min-h-0 flex-1 overflow-hidden"
      :class="editMode ? 'pt-7' : ''"
      @dblclick="!editMode && emit('edit-config', widget.id)"
    >
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

    <!-- Loading overlay -->
    <div
      v-if="loading"
      class="absolute inset-0 z-20 flex items-center justify-center bg-white/60 backdrop-blur-sm"
    >
      <RefreshCw class="h-5 w-5 animate-spin text-indigo-400" />
    </div>

    <!-- Error state -->
    <div
      v-if="error"
      class="absolute inset-x-0 bottom-0 z-20 flex items-center gap-2 bg-rose-50 px-3 py-1.5 border-t border-rose-100"
    >
      <span class="flex-1 text-[11px] text-rose-600 truncate">{{ error }}</span>
      <button
        class="flex-shrink-0 text-[11px] font-medium text-rose-600 hover:text-rose-800"
        @click="refresh()"
      >
        Retry
      </button>
      <button
        v-if="hasDataSource"
        class="flex-shrink-0 text-[11px] font-medium text-indigo-600 hover:text-indigo-800"
        @click="emit('open-sql-editor', widget.id, error ?? undefined)"
      >
        Fix
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue'
import { GripVertical, X, RefreshCw, Code, Settings } from 'lucide-vue-next'
import type { DashboardWidget } from '~/types/dashboard'
import { useWidgetData } from '~/composables/useWidgetData'

const props = defineProps<{
  widget: DashboardWidget
  editMode: boolean
}>()

const emit = defineEmits<{
  remove: [id: string]
  'open-sql-editor': [id: string, error?: string]
  'edit-config': [id: string]
}>()

const widgetRef = toRef(props, 'widget')
const { loading, error, lastRefreshedAt, hasDataSource, refresh } = useWidgetData(widgetRef)

const WIDGET_TYPE_LABELS: Record<string, string> = {
  kpi: 'Score Chart',
  chart: 'Chart',
  table: 'Table',
  text: 'Text',
  filter: 'Filter',
}

const widgetDisplayName = computed(() =>
  WIDGET_TYPE_LABELS[props.widget.widget.type] ?? props.widget.widget.type,
)

function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}
</script>
