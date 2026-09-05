<template>
  <div class="relative flex h-full flex-col overflow-hidden">

    <!-- Edit mode: drag handle + controls overlay -->
    <div
      v-if="editMode"
      class="absolute inset-x-0 top-0 z-10 flex items-center justify-between bg-[var(--paper-0)]/90 dark:bg-neutral-800/90 px-3 py-1.5 border-b border-[var(--line)] dark:border-neutral-700 backdrop-blur-sm"
    >
      <div class="widget-drag-handle flex cursor-grab items-center gap-1.5 active:cursor-grabbing">
        <GripVertical class="h-3.5 w-3.5 text-[var(--ink-3)]" />
        <span v-if="widget.title" class="text-sm font-medium text-[var(--ink-2)] truncate max-w-[140px]">{{ widget.title }}</span>
        <span v-else class="text-sm text-[var(--ink-3)]">{{ widgetDisplayName }}</span>
      </div>
      <div class="flex items-center gap-1">
        <button
          v-if="hasDataSource"
          class="flex h-5 w-5 items-center justify-center rounded text-[var(--ink-3)] hover:bg-[var(--ember-wash)] hover:text-[var(--ember)] transition-colors"
          title="View SQL query"
          @click="emit('open-sql-editor', widget.id)"
        >
          <Code class="h-3 w-3" />
        </button>
        <button
          v-if="canRefresh"
          class="flex h-5 w-5 items-center justify-center rounded text-[var(--ink-3)] hover:bg-[var(--ember-wash)] hover:text-[var(--ember)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          :disabled="loading"
          title="Refresh data"
          @click.stop="refresh()"
        >
          <RefreshCw class="h-3 w-3" :class="{ 'animate-spin': loading }" />
        </button>
        <button
          class="flex h-5 w-5 items-center justify-center rounded text-[var(--ink-3)] hover:bg-[var(--ember-wash)] hover:text-[var(--ember)] transition-colors"
          title="Duplicate widget"
          @click="emit('duplicate', widget.id)"
        >
          <Copy class="h-3 w-3" />
        </button>
        <button
          class="flex h-5 w-5 items-center justify-center rounded text-[var(--ink-3)] hover:bg-indigo-50 hover:text-indigo-500 transition-colors"
          title="Edit widget"
          @click.stop="emit('edit-config', widget.id)"
        >
          <Settings class="h-3 w-3" />
        </button>
        <button
          class="flex h-5 w-5 items-center justify-center rounded text-[var(--ink-3)] hover:bg-rose-50 hover:text-rose-500 transition-colors"
          @click="emit('remove', widget.id)"
        >
          <X class="h-3 w-3" />
        </button>
      </div>
    </div>

    <!-- View mode: full header row only when widget has a custom title -->
    <div v-if="!editMode && widget.title" class="widget-header">
      <span class="widget-label">{{ widget.title }}</span>
      <button
        v-if="canRefresh"
        class="icon-btn"
        title="Refresh data"
        :disabled="loading"
        @click="refresh()"
      >
        <RefreshCw class="h-3 w-3" :class="{ 'animate-spin': loading }" />
      </button>
    </div>
    <!-- Floating refresh for data widgets without a custom title (view mode) -->
    <button
      v-else-if="!editMode && canRefresh"
      class="refresh-float"
      title="Refresh data"
      :disabled="loading"
      @click="refresh()"
    >
      <RefreshCw class="h-3 w-3" :class="{ 'animate-spin': loading }" />
    </button>

    <!-- Widget body.
         Dimmed while a refresh is in flight over data we're still painting:
         the numbers on screen are the previous filter's, and a spinning 12px
         icon alone doesn't say so — it reads as a frozen page. -->
    <div
      class="min-h-0 flex-1 overflow-hidden transition-opacity duration-200"
      :class="[editMode ? 'pt-7' : '', loading && hasData ? 'opacity-50' : '']"
      @click="editMode && emit('edit-config', widget.id)"
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
        :widget-id="widget.id"
        :config="widget.widget.config"
        :edit-mode="editMode"
      />
      <DashboardWidgetPivotTable
        v-else-if="widget.widget.type === 'pivot_table'"
        :widget-id="widget.id"
        :config="widget.widget.config"
        :edit-mode="editMode"
      />
      <DashboardWidgetText
        v-else-if="widget.widget.type === 'text'"
        :widget-id="widget.id"
        :config="widget.widget.config"
        :edit-mode="editMode"
      />
      <DashboardWidgetFilter
        v-else-if="widget.widget.type === 'filter'"
        :widget-id="widget.id"
        :config="widget.widget.config"
      />
      <DashboardWidgetSection
        v-else-if="widget.widget.type === 'section'"
        :widget-id="widget.id"
        :config="widget.widget.config"
        :edit-mode="editMode"
      />
    </div>

    <!-- Provenance footer (view mode only) -->
    <div
      v-if="!editMode && (sourceLabel || lastRefreshedAt)"
      class="widget-footer"
    >
      <span v-if="sourceLabel" class="provenance" :title="`from ${sourceLabel}`">
        <span class="provenance-prefix">↗ from</span>
        <span class="provenance-source">{{ sourceLabel }}</span>
      </span>
      <span v-else class="provenance-empty" />
      <span v-if="lastRefreshedAt" class="age" :title="lastRefreshedAt">{{ formatRelativeTime(lastRefreshedAt) }}</span>
    </div>

    <!-- Loading skeleton — only when there's no stored data to paint;
         widgets with data keep showing it while a refresh is in flight -->
    <div v-if="loading && !hasData" class="absolute inset-0 z-20 bg-[var(--paper-0)] dark:bg-neutral-800">
      <DashboardWidgetSkeleton :type="widget.widget.type" />
    </div>

    <!-- Error state -->
    <div
      v-if="error"
      class="absolute inset-x-0 bottom-0 z-20 flex items-center gap-2 bg-rose-50 px-3 py-1.5 border-t border-rose-100"
    >
      <span class="flex-1 text-sm text-rose-600 truncate">{{ error }}</span>
      <button
        v-if="canRefresh"
        class="flex-shrink-0 text-sm font-medium text-rose-600 hover:text-rose-800"
        @click="refresh()"
      >
        Retry
      </button>
      <button
        v-if="hasDataSource"
        class="flex-shrink-0 text-sm font-medium text-[var(--ember)] hover:text-[var(--d-moss)]"
        @click="emit('open-sql-editor', widget.id, error ?? undefined)"
      >
        Fix
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { GripVertical, X, RefreshCw, Code, Copy, Settings } from 'lucide-vue-next'
import type { DashboardWidget } from '~/types/dashboard'
import { useWidgetData } from '~/composables/useWidgetData'
import { useConnections } from '~/composables/useConnections'
import { parseUtcDate } from '~/utils/format'
import { hasRenderableData } from '~/utils/widgetRender'

const props = withDefaults(defineProps<{
  widget: DashboardWidget
  editMode: boolean
  // Briefing and chat-chart embeds render a generation-time snapshot and pass
  // false: no live re-query, and no manual refresh either — re-running the query
  // would rewrite the historical answer the snapshot froze. Dashboards leave it
  // true (default) so widgets refresh.
  autoRefresh?: boolean
  // Which dashboard this widget belongs to, for embeds rendering a widget of a
  // dashboard the store is not on. Omitted on the dashboard page.
  dashboardId?: number | null
}>(), { autoRefresh: true })

const emit = defineEmits<{
  remove: [id: string]
  duplicate: [id: string]
  'open-sql-editor': [id: string, error?: string]
  'edit-config': [id: string]
}>()

const widgetRef = toRef(props, 'widget')
const { loading, error, lastRefreshedAt, hasDataSource, refresh } = useWidgetData(
  widgetRef, props.autoRefresh, { dashboardId: props.dashboardId },
)
const canRefresh = computed(() => hasDataSource.value && props.autoRefresh)

const WIDGET_TYPE_LABELS: Record<string, string> = {
  kpi: 'KPI',
  chart: 'Chart',
  table: 'Table',
  pivot_table: 'Pivot Table',
  text: 'Text',
  filter: 'Filter',
  section: 'Section',
}

const widgetDisplayName = computed(() =>
  WIDGET_TYPE_LABELS[props.widget.widget.type] ?? props.widget.widget.type,
)

const hasData = computed(() => hasRenderableData(props.widget))

// Provenance label: the uploaded filename, never the internal storage table
// name. Only fetch connections when there's one to resolve — public briefing
// embeds have `dataSource` scrubbed server-side and are unauthenticated.
const { ensureLoaded: ensureConnectionsLoaded, getSourceLabel } = useConnections()
if (props.widget.dataSource?.connectionId) ensureConnectionsLoaded()

const sourceLabel = computed(() => {
  const connectionId = props.widget.dataSource?.connectionId
  return connectionId ? getSourceLabel(connectionId) : null
})

function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - parseUtcDate(isoString).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  return `${Math.floor(hours / 24)}d`
}
</script>

<style scoped>
.widget-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 4px;
  flex-shrink: 0;
}

.refresh-float {
  position: absolute;
  top: 8px;
  right: 10px;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 5px;
  color: var(--ink-3);
  transition: background 0.1s, color 0.1s;
}
.refresh-float:hover { background: var(--paper-2); color: var(--ink-2); }
.refresh-float:disabled { opacity: 0.4; cursor: not-allowed; }

.widget-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 14px 10px;
  flex-shrink: 0;
  border-top: 1px solid var(--line);
  margin-top: auto;
  min-width: 0;
  overflow: hidden;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 5px;
  color: var(--ink-3);
  transition: background 0.1s, color 0.1s;
}
.icon-btn:hover { background: var(--paper-2); color: var(--ink-2); }
.icon-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.provenance {
  font-family: var(--font-sans);
  font-size: 14px;
  color: var(--ink-3);
  display: flex;
  align-items: center;
  gap: 3px;
  min-width: 0;
  flex: 1 1 auto;
  white-space: nowrap;
  overflow: hidden;
}
.provenance-prefix {
  flex-shrink: 0;
}
.provenance-source {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.age {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--ink-3);
  opacity: 0.55;
  flex-shrink: 0;
  white-space: nowrap;
}

</style>
