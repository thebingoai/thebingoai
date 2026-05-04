<template>
  <div class="flex h-full flex-col overflow-hidden">
    <div v-if="config.title" class="flex-shrink-0 px-4 pt-3 pb-1">
      <span class="widget-label">{{ config.title }}</span>
    </div>

    <!-- Table wrapper: horizontal scroll is opt-in -->
    <div class="flex-1 overflow-auto" :class="config.horizontalScrolling ? 'overflow-x-auto' : ''">
      <table class="w-full text-sm">

        <!-- Header -->
        <thead
          v-if="config.showHeader !== false"
          class="sticky top-0 bg-white border-b border-gray-100 dark:bg-neutral-800 dark:border-neutral-700"
        >
          <tr>
            <!-- Row number header -->
            <th
              v-if="config.showRowNumbers"
              class="px-3 py-2.5 text-left text-xs font-medium text-gray-300 uppercase tracking-wide w-8"
            >#</th>

            <th
              v-for="col in config.columns"
              :key="col.key"
              class="px-4 py-2.5 text-xs font-medium text-gray-400 uppercase tracking-wide dark:text-neutral-400"
              :class="[
                col.sortable ? 'cursor-pointer hover:text-gray-600 dark:hover:text-neutral-200 select-none' : '',
                colAlignClass(col),
                config.wrapText ? '' : 'whitespace-nowrap',
              ]"
              @click="col.sortable && toggleSort(col.key)"
            >
              <div
                class="flex items-center gap-1"
                :class="col.align === 'right' ? 'justify-end' : col.align === 'center' ? 'justify-center' : ''"
              >
                {{ col.label }}
                <span v-if="col.sortable && sortKey === col.key" class="text-gray-500 dark:text-neutral-400">
                  {{ sortDir === 'asc' ? '↑' : '↓' }}
                </span>
              </div>
            </th>
          </tr>

          <!-- Column filter row -->
          <tr v-if="hasFilterableColumns">
            <th v-if="config.showRowNumbers" />
            <th v-for="col in config.columns" :key="col.key" class="px-4 py-1">
              <input
                v-if="col.filterable"
                v-model="columnFilters[col.key]"
                type="text"
                placeholder="Filter..."
                class="w-full rounded border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-600 font-normal focus:outline-none focus:ring-1 focus:ring-indigo-300 dark:border-neutral-600 dark:bg-neutral-700 dark:text-neutral-300 dark:placeholder-neutral-500"
              />
            </th>
          </tr>
        </thead>

        <!-- Body -->
        <tbody class="divide-y divide-gray-50 dark:divide-neutral-700">
          <tr
            v-for="(row, i) in displayRows"
            :key="i"
            class="hover:bg-gray-50 transition-colors dark:hover:bg-neutral-700/50"
            :class="config.stripedRows && i % 2 === 1 ? 'bg-gray-50/60 dark:bg-neutral-800/40' : ''"
          >
            <!-- Row number cell -->
            <td
              v-if="config.showRowNumbers"
              class="px-3 py-2.5 text-[11px] text-gray-300 tabular-nums w-8 dark:text-neutral-600"
            >{{ rowOffset + i + 1 }}</td>

            <td
              v-for="col in config.columns"
              :key="col.key"
              class="px-4 py-2.5 dark:text-neutral-300"
              :class="[
                colAlignClass(col),
                config.wrapText ? '' : 'whitespace-nowrap',
                isNumericFormat(col) ? 'tabular-nums' : '',
              ]"
              :style="col.displayType === 'heatmap' ? heatmapCellStyle(row[col.key], col.key) : undefined"
            >
              <!-- Bar display -->
              <template v-if="col.displayType === 'bar' && row[col.key] != null">
                <div class="flex items-center gap-2">
                  <div class="flex-1 h-2 rounded-full overflow-hidden" style="background:rgba(99,102,241,0.12);">
                    <div
                      class="h-full rounded-full transition-all"
                      :style="{
                        width: barWidth(row[col.key], col.key) + '%',
                        background: colColor(col.key),
                      }"
                    />
                  </div>
                  <span v-if="col.showBarValue !== false" class="text-xs min-w-[40px] text-right">
                    {{ formatCell(row[col.key], col) }}
                  </span>
                </div>
              </template>

              <!-- Default / number / heatmap text -->
              <template v-else>
                <span :class="getCellClass(row[col.key], col.format)">
                  {{ formatCell(row[col.key], col) }}
                </span>
              </template>
            </td>
          </tr>
        </tbody>

        <!-- Summary row -->
        <tfoot v-if="config.showSummaryRow">
          <tr class="border-t-2 border-gray-200 bg-gray-50 dark:border-neutral-600 dark:bg-neutral-800">
            <td v-if="config.showRowNumbers" class="px-3 py-2.5 text-[11px] text-gray-300">Σ</td>
            <td
              v-for="col in config.columns"
              :key="col.key"
              class="px-4 py-2.5 text-xs font-semibold text-gray-700 dark:text-neutral-300"
              :class="[colAlignClass(col), isNumericFormat(col) ? 'tabular-nums' : '']"
            >
              {{ summaryValue(col) }}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>

    <!-- Pagination controls -->
    <div
      v-if="config.pagination && totalPages > 1"
      class="flex items-center justify-between flex-shrink-0 border-t border-gray-100 px-4 py-2 dark:border-neutral-700"
    >
      <span class="text-xs text-gray-400 dark:text-neutral-500">
        {{ rowOffset + 1 }}–{{ Math.min(rowOffset + rowsPerPage, sortedRows.length) }}
        of {{ sortedRows.length }}
      </span>
      <div class="flex items-center gap-1">
        <button
          :disabled="currentPage <= 1"
          class="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed dark:text-neutral-400 dark:hover:bg-neutral-700"
          @click="currentPage--"
        >Prev</button>
        <span class="text-xs text-gray-400 px-1 dark:text-neutral-500">{{ currentPage }} / {{ totalPages }}</span>
        <button
          :disabled="currentPage >= totalPages"
          class="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed dark:text-neutral-400 dark:hover:bg-neutral-700"
          @click="currentPage++"
        >Next</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import type { TableWidgetConfig, TableColumn } from '~/types/dashboard'
import { parseUtcDate } from '~/utils/format'

const THEME_COLOR = '#6366f1'
const NUMERIC_FORMATS = new Set(['number', 'currency', 'percent'])

const props = defineProps<{
  config: TableWidgetConfig
}>()

const sortKey = ref<string | null>(null)
const sortDir = ref<'asc' | 'desc'>('asc')
const currentPage = ref(1)
const columnFilters = ref<Record<string, string>>({})

onMounted(() => {
  if (props.config.defaultSortKey) {
    sortKey.value = props.config.defaultSortKey
    sortDir.value = props.config.defaultSortDir ?? 'asc'
  }
})

watch(
  () => [props.config.defaultSortKey, props.config.defaultSortDir] as const,
  ([key, dir]) => {
    if (key && sortKey.value === null) {
      sortKey.value = key
      sortDir.value = dir ?? 'asc'
    }
  },
)

const rowsPerPage = computed(() => props.config.rowsPerPage ?? 25)
const hasFilterableColumns = computed(() => props.config.columns.some(c => c.filterable))

function isNumericFormat(col: TableColumn): boolean {
  return NUMERIC_FORMATS.has(col.format ?? '')
}

function colAlignClass(col: TableColumn): string {
  if (col.align === 'right') return 'text-right'
  if (col.align === 'center') return 'text-center'
  return 'text-left'
}

function colColor(key: string): string {
  return props.config.columnColors?.[key] ?? THEME_COLOR
}

// Per-column max/min for bar width and heatmap intensity
const colMaxValues = computed(() => {
  const map: Record<string, number> = {}
  for (const col of props.config.columns) {
    if (col.displayType === 'bar' || col.displayType === 'heatmap') {
      const vals = (props.config.rows ?? [])
        .map(r => Number(r[col.key]))
        .filter(v => isFinite(v))
      map[col.key] = vals.length ? Math.max(...vals) : 0
    }
  }
  return map
})

const colMinValues = computed(() => {
  const map: Record<string, number> = {}
  for (const col of props.config.columns) {
    if (col.displayType === 'heatmap') {
      const vals = (props.config.rows ?? [])
        .map(r => Number(r[col.key]))
        .filter(v => isFinite(v))
      map[col.key] = vals.length ? Math.min(...vals) : 0
    }
  }
  return map
})

function barWidth(value: any, key: string): number {
  const max = colMaxValues.value[key]
  if (!max) return 0
  return Math.max(0, Math.min(100, (Number(value) / max) * 100))
}

function heatmapCellStyle(value: any, key: string): Record<string, string> {
  if (value == null) return {}
  const min = colMinValues.value[key] ?? 0
  const max = colMaxValues.value[key] ?? 0
  const intensity = max === min ? 0.5 : Math.max(0, Math.min(1, (Number(value) - min) / (max - min)))
  const color = colColor(key)
  // Opacity range: 5% (min) → 35% (max) encoded as 2-digit hex appended to the hex color
  const opacityHex = Math.round(intensity * 76 + 13).toString(16).padStart(2, '0')
  return { background: `${color}${opacityHex}` }
}

// Filtering
const filteredRows = computed(() => {
  let rows = props.config.rows ?? []
  for (const [key, filterVal] of Object.entries(columnFilters.value)) {
    if (!filterVal) continue
    const lower = filterVal.toLowerCase()
    rows = rows.filter(row => String(row[key] ?? '').toLowerCase().includes(lower))
  }
  return rows
})

// Sorting
const sortedRows = computed(() => {
  if (!sortKey.value) return filteredRows.value
  const key = sortKey.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...filteredRows.value].sort((a, b) => {
    const av = a[key]; const bv = b[key]
    if (av == null) return 1
    if (bv == null) return -1
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir
    return String(av).localeCompare(String(bv)) * dir
  })
})

function toggleSort(key: string) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  }
  else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

// Pagination
const totalPages = computed(() =>
  Math.max(1, Math.ceil(sortedRows.value.length / rowsPerPage.value)),
)

const rowOffset = computed(() =>
  props.config.pagination ? (currentPage.value - 1) * rowsPerPage.value : 0,
)

const displayRows = computed(() => {
  if (!props.config.pagination) return sortedRows.value
  return sortedRows.value.slice(rowOffset.value, rowOffset.value + rowsPerPage.value)
})

watch([() => props.config.rows, columnFilters], () => { currentPage.value = 1 }, { deep: true })

// Summary row
function summaryValue(col: TableColumn): string {
  if (!isNumericFormat(col)) return '—'
  const sum = sortedRows.value.reduce((acc, row) => {
    const v = Number(row[col.key])
    return acc + (isFinite(v) ? v : 0)
  }, 0)
  return formatCell(sum, col)
}

// Cell formatting
function missingValue(): string {
  switch (props.config.missingDataDisplay) {
    case 'blank': return ''
    case 'noData': return 'No data'
    default: return '—'
  }
}

function formatCell(value: any, col: TableColumn): string {
  if (value == null) return missingValue()
  const dp = col.decimalPlaces ?? 2
  const round = !!col.roundValue
  switch (col.format) {
    case 'currency': {
      const num = Number(value)
      if (round) return '$' + num.toFixed(dp).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
      return '$' + num.toLocaleString()
    }
    case 'number': {
      const num = Number(value)
      if (round) return num.toFixed(dp).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
      return num.toLocaleString()
    }
    case 'percent': {
      const num = Number(value)
      const formatted = round ? num.toFixed(dp) : num.toFixed(1)
      return (num > 0 ? '+' : '') + formatted + '%'
    }
    case 'date':
      return parseUtcDate(value).toLocaleDateString()
    default:
      return String(value)
  }
}

function getCellClass(value: any, format?: string): string {
  if (format === 'percent' && typeof value === 'number') {
    return value > 0 ? 'text-emerald-600' : value < 0 ? 'text-rose-500' : ''
  }
  return ''
}

// CSV export (exposed for parent)
function exportCsv() {
  const headers = props.config.columns.map(c => escapeCsvField(c.label))
  const rows = sortedRows.value.map(row =>
    props.config.columns.map(col => escapeCsvField(String(row[col.key] ?? ''))).join(','),
  )
  const csv = [headers.join(','), ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'table-export.csv'
  a.click()
  URL.revokeObjectURL(url)
}

function escapeCsvField(str: string): string {
  if (str.includes(',') || str.includes('\n') || str.includes('"')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

defineExpose({ exportCsv })
</script>
