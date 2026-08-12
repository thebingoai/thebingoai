<template>
  <div
    class="rounded-lg border border-neutral-100 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4"
    :style="{ height: heightPx + 'px' }"
  >
    <DashboardWidget :widget="chartRef.widget" :auto-refresh="false" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

// Frozen ad-hoc chart snapshot — config + data are already embedded in
// chartRef.widget (built server-side, never re-queried from chat). No fetch,
// no live refresh — mirrors BriefingWidgetEmbed's `snapshot` mode but with
// no dashboardId/widgetId to fetch by, since this widget was never persisted.
const props = defineProps<{
  chartRef: { kind: 'adhoc'; widget: any; connection_id: number }
}>()

// DashboardWidget assumes a GridStack ancestor with an explicit pixel height
// (cellHeight: 70 per unit — see useDashboardGrid.ts) and renders at h-full.
// Outside the grid there's nothing to resolve that against: Chart.js canvases
// fall back to an intrinsic default size, but percentage/flex-height renderers
// like DashboardWidgetFunnel collapse to 0px. Mirror the grid's cellHeight so
// every widget type gets the same real height it would on a dashboard.
const GRID_CELL_HEIGHT = 70
const heightPx = computed(() => (props.chartRef.widget?.position?.h ?? 5) * GRID_CELL_HEIGHT)
</script>
