<template>
  <div v-if="widget && widget.widget?.config" class="rounded-lg border border-neutral-100 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4">
    <DashboardWidget :widget="widget" :auto-refresh="!snapshot" :edit-mode="false" :dashboard-id="dashboardId" />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  widgetId: string | number
  // Authed view only: used to fetch the widget shape. Omitted on the public
  // share view, which passes `widget` inline instead.
  dashboardId?: number
  // Rendered data config snapshot from generation time. When present we merge
  // it instead of re-running the widget's SQL — instant render, no live query.
  snapshot?: Record<string, any>
  // Public share view: the widget shape, already stripped of dataSource by the
  // backend. When present we skip the authed fetch entirely — an anonymous
  // visitor has no token for it. A stripped widget also carries no dataSource,
  // so the refresh() branch below cannot fire even by accident.
  widget?: Record<string, any>
}>()

const emit = defineEmits<{ loaded: [] }>()

const { fetchWithRefresh } = useApi()
const widget = ref<any>(null)
// DashboardWidget only refreshes on click; briefing embeds render the saved
// (data-less) config. Pull the widget's data on mount so charts/KPIs populate.
// Skip useWidgetData's auto-refresh watcher when a snapshot is present — the
// snapshot populates the config below, so a live re-query would be redundant.
// dashboardId: the widget belongs to THAT dashboard, not whichever one the
// dashboard store was last on (on /chat and /briefings it is reset entirely).
const { refresh } = useWidgetData(widget as any, !props.snapshot, { dashboardId: props.dashboardId })

onMounted(async () => {
  try {
    widget.value = props.widget
      // Deep clone: the snapshot merge below Object.assigns into
      // widget.widget.config, and a shallow copy would write straight through
      // into the caller's prop object.
      ? structuredClone(toRaw(props.widget))
      : props.dashboardId != null
        ? await fetchWithRefresh(
            `/api/dashboards/${props.dashboardId}/widgets/${props.widgetId}`,
            { method: 'GET' },
          )
        : null
    // widget.value can be null with a snapshot still present: the backend
    // serves widget_snapshots unfiltered, so a widget deleted from the
    // dashboard before share time has a snapshot but no frozen shape. A
    // snapshot alone can't render (no widget config) — skip, don't throw.
    if (props.snapshot && widget.value) {
      // Snapshot present (generated post-rollout): merge the saved data config,
      // no SQL round-trip. mergeRefreshedConfig preserves editor-only columns.
      const { mergeRefreshedConfig } = await import('~/utils/widgetMerge')
      Object.assign(widget.value.widget.config, mergeRefreshedConfig(widget.value, { ...props.snapshot }))
    } else if (widget.value?.dataSource) {
      await refresh()
    }
  } catch {
    // widget deleted between briefing-time and view-time — silent drop
    widget.value = null
  } finally {
    // Always signal completion — even a dropped widget must not stall the PDF wait.
    emit('loaded')
  }
})
</script>
