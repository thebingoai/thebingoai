<template>
  <div class="w-[380px] flex-shrink-0 border-l border-gray-200 flex flex-col h-full overflow-hidden bg-white">

    <!-- Header -->
    <div class="flex flex-shrink-0 items-center gap-3 border-b border-gray-100 px-5 py-3.5">
      <button
        class="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
        @click="emit('close')"
      >
        <X class="h-4 w-4" />
      </button>
      <div class="min-w-0">
        <h2 class="text-sm font-semibold text-gray-900">Edit Widget</h2>
        <p class="text-[11px] text-gray-400">{{ widgetTypeLabel }}</p>
      </div>
      <div class="ml-auto flex items-center gap-2">
        <span v-if="!editMode" class="text-[11px] text-gray-400">View only</span>
      </div>
    </div>

    <!-- Common meta fields -->
    <div class="flex-shrink-0 border-b border-gray-100 bg-gray-50 px-5 py-3 space-y-2">
      <div class="space-y-1">
        <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Title</label>
        <input
          v-model="localTitle"
          type="text"
          placeholder="Widget title (optional)"
          class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors"
          :readonly="!editMode"
          :class="!editMode ? 'cursor-default bg-gray-50' : ''"
          @input="saveMeta()"
        />
      </div>
      <div class="space-y-1">
        <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Description</label>
        <input
          v-model="localDescription"
          type="text"
          placeholder="Widget description (optional)"
          class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors"
          :readonly="!editMode"
          :class="!editMode ? 'cursor-default bg-gray-50' : ''"
          @input="saveMeta()"
        />
      </div>
    </div>

    <!-- Tab bar (only for data widgets) -->
    <div v-if="isDataWidget" class="flex flex-shrink-0 border-b border-gray-200 px-5">
      <button
        class="px-3 py-2 text-sm font-medium border-b-2 transition-colors"
        :class="activeTab === 'configure'
          ? 'border-indigo-500 text-indigo-600'
          : 'border-transparent text-gray-500 hover:text-gray-700'"
        @click="activeTab = 'configure'"
      >
        Configure
      </button>
      <button
        class="px-3 py-2 text-sm font-medium border-b-2 transition-colors"
        :class="activeTab === 'data'
          ? 'border-indigo-500 text-indigo-600'
          : 'border-transparent text-gray-500 hover:text-gray-700'"
        @click="activeTab = 'data'"
      >
        Data Source
      </button>
    </div>

    <!-- Tab content area -->
    <div class="flex-1 min-h-0 overflow-hidden">

      <!-- Configure tab (or full area for text widgets) -->
      <div
        v-if="!isDataWidget || activeTab === 'configure'"
        class="h-full overflow-hidden"
      >
        <component
          :is="editorComponent"
          v-if="editorComponent"
          :model-value="currentConfig"
          :edit-mode="editMode"
          class="h-full"
          @update:model-value="onConfigUpdate"
        />
        <div v-else class="flex h-full items-center justify-center p-10 text-sm text-gray-400">
          Configuration editor not yet available for this widget type.
        </div>
      </div>

      <!-- Data Source tab -->
      <div
        v-else-if="activeTab === 'data'"
        class="h-full overflow-y-auto px-5 py-3 space-y-3"
      >
        <div class="flex items-center justify-between">
          <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">SQL Data Source</h3>
          <button
            class="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            :disabled="testLoading || !props.widget.dataSource"
            @click="testQuery()"
          >
            <RefreshCw class="h-3 w-3" :class="{ 'animate-spin': testLoading }" />
            Test Query
          </button>
        </div>

        <!-- Connection picker -->
        <div class="space-y-1">
          <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Connection</label>
          <select
            v-model="selectedConnectionId"
            :disabled="!editMode"
            class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
            @change="onConnectionChange()"
          >
            <option :value="null" disabled>Select a connection…</option>
            <option v-for="conn in connections" :key="conn.id" :value="conn.id">
              {{ conn.name }}
            </option>
          </select>
        </div>

        <!-- SQL textarea -->
        <textarea
          v-model="localSql"
          :readonly="!editMode"
          rows="5"
          class="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 font-mono text-xs text-gray-800 leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors"
          :class="editMode ? 'bg-white' : 'cursor-default'"
          spellcheck="false"
          @blur="onSqlBlur()"
        />

        <!-- Column mapping display (only when dataSource exists) -->
        <DashboardMappingDisplay v-if="props.widget.dataSource" :mapping="props.widget.dataSource.mapping" />

        <!-- Preview error -->
        <div v-if="previewError" class="rounded-lg bg-rose-50 border border-rose-100 px-3 py-2 text-xs text-rose-600">
          <div class="flex items-start justify-between gap-2">
            <span class="flex-1">{{ previewError }}</span>
            <button
              v-if="editMode && widget.dataSource"
              class="flex-shrink-0 flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium bg-indigo-50 text-indigo-600 hover:bg-indigo-100 disabled:opacity-40"
              :disabled="suggestLoading"
              @click="suggestFix()"
            >
              <Sparkles class="h-3 w-3" :class="{ 'animate-pulse': suggestLoading }" />
              {{ suggestLoading ? 'Analyzing...' : 'Suggest Fix' }}
            </button>
          </div>
        </div>

        <!-- AI suggestion explanation -->
        <div v-if="suggestion" class="rounded-lg bg-indigo-50 border border-indigo-100 px-3 py-2 text-xs text-indigo-700">
          <Sparkles class="h-3.5 w-3.5 inline mr-1" />
          <span class="font-medium">AI Fix Applied:</span> {{ suggestion.explanation }}
        </div>

        <!-- Preview table -->
        <div v-else-if="previewRows.length > 0" class="space-y-1">
          <div class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Preview ({{ previewRows.length }} rows)</div>
          <div class="overflow-x-auto rounded-lg border border-gray-100">
            <table class="w-full text-xs">
              <thead class="bg-gray-50">
                <tr>
                  <th
                    v-for="col in previewColumns"
                    :key="col"
                    class="px-3 py-1.5 text-left font-medium text-gray-500"
                  >{{ col }}</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-50">
                <tr v-for="(row, i) in previewRows" :key="i" class="hover:bg-gray-50">
                  <td v-for="(val, j) in row" :key="j" class="px-3 py-1.5 text-gray-700 font-mono">{{ val }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineAsyncComponent } from 'vue'

// Defined at module level so they're singletons, not re-created on each setup call
const editorComponents: Record<string, ReturnType<typeof defineAsyncComponent>> = {
  text: defineAsyncComponent(() => import('./WidgetEditorText.vue')),
  kpi: defineAsyncComponent(() => import('./WidgetEditorKpi.vue')),
  table: defineAsyncComponent(() => import('./WidgetEditorTable.vue')),
  chart: defineAsyncComponent(() => import('./WidgetEditorChart.vue')),
}
</script>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { X, RefreshCw, Sparkles } from 'lucide-vue-next'
import type { DashboardWidget, WidgetConfig, WidgetDataSource } from '~/types/dashboard'
import { useDashboardStore } from '~/stores/dashboard'
import { useApi } from '~/composables/useApi'
import DashboardMappingDisplay from '~/components/dashboard/DashboardMappingDisplay.vue'

const DATA_WIDGET_TYPES = new Set(['chart', 'kpi', 'table'])

const props = defineProps<{
  widget: DashboardWidget
  editMode: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const store = useDashboardStore()
const api = useApi()

// Tab state (only relevant for data widgets)
const activeTab = ref<'configure' | 'data'>('configure')

// Local meta state (title/description)
const localTitle = ref(props.widget.title ?? '')
const localDescription = ref(props.widget.description ?? '')

// SQL section state
const localSql = ref(props.widget.dataSource?.sql ?? '')
const selectedConnectionId = ref<number | null>(props.widget.dataSource?.connectionId ?? null)
const connections = ref<{ id: number; name: string }[]>([])
const testLoading = ref(false)
const previewColumns = ref<string[]>([])
const previewRows = ref<any[][]>([])
const previewError = ref<string | null>(null)
const suggestLoading = ref(false)
const suggestion = ref<{ suggested_sql: string; explanation: string } | null>(null)

const isDataWidget = computed(() => DATA_WIDGET_TYPES.has(props.widget.widget.type))

// Current config is read from the store so the widget on canvas stays in sync
const currentConfig = computed(() => props.widget.widget)

const WIDGET_TYPE_LABELS: Record<string, string> = {
  kpi: 'Score Chart',
  chart: 'Chart',
  table: 'Table',
  text: 'Text',
  filter: 'Filter',
}

const widgetTypeLabel = computed(() =>
  WIDGET_TYPE_LABELS[props.widget.widget.type] ?? props.widget.widget.type,
)

const editorComponent = computed(() =>
  editorComponents[props.widget.widget.type] ?? null,
)

/** Reset local state when a different widget is selected */
watch(() => props.widget.id, () => {
  localTitle.value = props.widget.title ?? ''
  localDescription.value = props.widget.description ?? ''
  localSql.value = props.widget.dataSource?.sql ?? ''
  selectedConnectionId.value = props.widget.dataSource?.connectionId ?? null
  previewColumns.value = []
  previewRows.value = []
  previewError.value = null
  suggestion.value = null
  activeTab.value = 'configure'
})

/** Live update: write directly to store so the widget on canvas reflects changes immediately */
function onConfigUpdate(newConfig: WidgetConfig) {
  store.updateWidgetConfig(props.widget.id, newConfig)
}

function saveMeta() {
  store.updateWidgetMeta(props.widget.id, {
    title: localTitle.value || undefined,
    description: localDescription.value || undefined,
  })
}

function getDefaultMapping(type: string): WidgetDataSource['mapping'] {
  if (type === 'chart') return { type: 'chart', labelColumn: '', datasetColumns: [] }
  if (type === 'kpi') return { type: 'kpi', valueColumn: '' }
  return { type: 'table', columnConfig: [] }
}

function onSqlBlur() {
  if (!props.editMode) return
  const ds = props.widget.dataSource
  if (ds) {
    if (localSql.value !== ds.sql) {
      store.updateWidgetSql(props.widget.id, localSql.value)
    }
  } else if (selectedConnectionId.value !== null && localSql.value.trim()) {
    // Create dataSource for the first time
    store.setWidgetDataSource(props.widget.id, {
      connectionId: selectedConnectionId.value,
      sql: localSql.value,
      mapping: getDefaultMapping(props.widget.widget.type),
    })
  }
}

function onConnectionChange() {
  if (!props.editMode) return
  const ds = props.widget.dataSource
  if (ds && selectedConnectionId.value !== null) {
    store.setWidgetDataSource(props.widget.id, {
      ...ds,
      connectionId: selectedConnectionId.value,
    })
  }
}

async function testQuery() {
  const ds = props.widget.dataSource
  if (!ds) return
  testLoading.value = true
  previewError.value = null
  previewColumns.value = []
  previewRows.value = []
  suggestion.value = null

  try {
    const response = await api.dashboards.refreshWidget({
      connection_id: ds.connectionId,
      sql: localSql.value,
      mapping: ds.mapping as any,
      limit: 10,
    }) as { config: any }

    const config = response.config
    if (ds.mapping.type === 'chart' && config.data) {
      previewColumns.value = ['Label', ...config.data.datasets.map((d: any) => d.label)]
      previewRows.value = config.data.labels.map((label: any, i: number) => [
        label,
        ...config.data.datasets.map((d: any) => d.data[i]),
      ])
    } else if (ds.mapping.type === 'kpi') {
      previewColumns.value = Object.keys(config)
      previewRows.value = [Object.values(config)]
    } else if (ds.mapping.type === 'table' && config.columns) {
      previewColumns.value = config.columns.map((c: any) => c.label)
      previewRows.value = config.rows.slice(0, 10).map((row: any) =>
        config.columns.map((c: any) => row[c.key]),
      )
    }
  } catch (err: any) {
    previewError.value = err?.data?.detail ?? err?.message ?? 'Query failed'
  } finally {
    testLoading.value = false
  }
}

async function suggestFix() {
  const ds = props.widget.dataSource
  if (!ds || !previewError.value) return
  suggestLoading.value = true
  try {
    const result = await api.dashboards.suggestFix({
      connection_id: ds.connectionId,
      sql: localSql.value,
      error_message: previewError.value,
      mapping: ds.mapping as any,
      widget_title: localTitle.value || props.widget.widget.config?.title || props.widget.widget.config?.label,
      widget_description: localDescription.value,
    })
    localSql.value = result.suggested_sql
    suggestion.value = result
    previewError.value = null
    store.updateWidgetSql(props.widget.id, result.suggested_sql)
  } catch (err: any) {
    previewError.value = err?.data?.detail ?? err?.message ?? 'Suggest fix failed'
  } finally {
    suggestLoading.value = false
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

onMounted(async () => {
  document.addEventListener('keydown', onKeydown)
  if (isDataWidget.value) {
    try {
      const data = await api.connections.list() as { id: number; name: string }[]
      connections.value = data
    } catch {
      // silently ignore — connections will just be empty
    }
  }
})
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>
