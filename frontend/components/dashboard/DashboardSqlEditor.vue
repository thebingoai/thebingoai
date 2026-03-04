<template>
  <!-- Backdrop -->
  <div class="absolute inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" @click.self="emit('close')">
    <div class="relative flex flex-col w-full max-w-2xl max-h-[85vh] bg-white rounded-xl shadow-2xl overflow-hidden">

      <!-- Header -->
      <div class="flex items-center justify-between px-5 py-3.5 border-b border-gray-100">
        <div>
          <h2 class="text-sm font-semibold text-gray-900">SQL Query</h2>
          <p class="text-[11px] text-gray-400 mt-0.5">{{ widgetTitle }}</p>
        </div>
        <button
          class="flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
          @click="emit('close')"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-y-auto p-5 space-y-4">

        <!-- SQL textarea -->
        <div class="space-y-1.5">
          <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Query</label>
          <textarea
            v-model="localSql"
            :readonly="!editMode"
            class="w-full h-40 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 font-mono text-xs text-gray-800 leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors"
            :class="editMode ? 'bg-white' : 'cursor-default'"
            spellcheck="false"
          />
        </div>

        <!-- Mapping display -->
        <DashboardMappingDisplay :mapping="widget.dataSource!.mapping" />

        <!-- Preview table -->
        <div v-if="previewError" class="rounded-lg bg-rose-50 border border-rose-100 px-3 py-2.5 text-xs text-rose-600">
          {{ previewError }}
        </div>
        <div v-else-if="previewRows.length > 0" class="space-y-1.5">
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

      <!-- Footer -->
      <div class="flex items-center justify-end gap-2 px-5 py-3 border-t border-gray-100 bg-gray-50">
        <button
          class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          :disabled="testLoading"
          @click="testQuery()"
        >
          <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': testLoading }" />
          Test Query
        </button>
        <button
          v-if="editMode"
          class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          :disabled="localSql === widget.dataSource!.sql"
          @click="save()"
        >
          <Save class="h-3.5 w-3.5" />
          Save
        </button>
        <button
          class="rounded-lg px-3 py-1.5 text-xs font-medium text-gray-500 hover:text-gray-800 transition-colors"
          @click="emit('close')"
        >
          Close
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { X, RefreshCw, Save } from 'lucide-vue-next'
import type { DashboardWidget } from '~/types/dashboard'
import { useApi } from '~/composables/useApi'
import { useDashboardStore } from '~/stores/dashboard'

const props = defineProps<{
  widget: DashboardWidget
  editMode: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const api = useApi()
const store = useDashboardStore()

const localSql = ref(props.widget.dataSource!.sql)

const testLoading = ref(false)
const previewColumns = ref<string[]>([])
const previewRows = ref<any[][]>([])
const previewError = ref<string | null>(null)

const widgetTitle = computed(() =>
  props.widget.title ?? props.widget.widget.type.charAt(0).toUpperCase() + props.widget.widget.type.slice(1),
)

async function testQuery() {
  const ds = props.widget.dataSource!
  testLoading.value = true
  previewError.value = null
  previewColumns.value = []
  previewRows.value = []

  try {
    const response = await api.dashboards.refreshWidget({
      connection_id: ds.connectionId,
      sql: localSql.value,
      mapping: ds.mapping as any,
      limit: 10,
    }) as { config: any }

    // Show raw query result as preview — extract from config shape
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

function save() {
  const dashboard = store.currentDashboard
  if (!dashboard) return

  const widget = dashboard.widgets.find(w => w.id === props.widget.id)
  if (!widget?.dataSource) return

  widget.dataSource.sql = localSql.value
  store.dirty = true
  emit('close')
}
</script>
