<template>
  <div class="flex h-full flex-col overflow-hidden">
    <!-- Export bar -->
    <div class="flex items-center justify-end flex-shrink-0 px-4 py-1 border-b border-gray-50">
      <button
        class="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors"
        @click="exportCsv()"
      >
        <Download class="h-3 w-3" />
        Export CSV
      </button>
    </div>

    <div class="flex-1 overflow-auto">
      <table class="w-full text-sm">
        <thead class="sticky top-0 bg-white border-b border-gray-100">
          <tr>
            <th
              v-for="col in config.columns"
              :key="col.key"
              class="px-4 py-2.5 text-left text-xs font-medium text-gray-400 uppercase tracking-wide whitespace-nowrap"
              :class="col.sortable ? 'cursor-pointer hover:text-gray-600 select-none' : ''"
              @click="col.sortable && toggleSort(col.key)"
            >
              <div class="flex items-center gap-1">
                {{ col.label }}
                <span v-if="col.sortable && sortKey === col.key" class="text-gray-500">
                  {{ sortDir === 'asc' ? '↑' : '↓' }}
                </span>
              </div>
            </th>
          </tr>
          <!-- Column filter row -->
          <tr v-if="hasFilterableColumns">
            <th v-for="col in config.columns" :key="col.key" class="px-4 py-1">
              <input
                v-if="col.filterable"
                v-model="columnFilters[col.key]"
                type="text"
                placeholder="Filter..."
                class="w-full rounded border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-600 font-normal focus:outline-none focus:ring-1 focus:ring-indigo-300"
              />
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-50">
          <tr
            v-for="(row, i) in displayRows"
            :key="i"
            class="hover:bg-gray-50 transition-colors"
          >
            <td
              v-for="col in config.columns"
              :key="col.key"
              class="px-4 py-2.5 text-gray-700 whitespace-nowrap"
              :class="col.format === 'currency' || col.format === 'number' || col.format === 'percent' ? 'tabular-nums' : ''"
            >
              <span :class="getCellClass(row[col.key], col.format)">
                {{ formatCell(row[col.key], col.format) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination controls -->
    <div
      v-if="config.pagination && totalPages > 1"
      class="flex items-center justify-between flex-shrink-0 border-t border-gray-100 px-4 py-2"
    >
      <span class="text-xs text-gray-400">
        {{ (currentPage - 1) * rowsPerPage + 1 }}–{{ Math.min(currentPage * rowsPerPage, sortedRows.length) }}
        of {{ sortedRows.length }}
      </span>
      <div class="flex items-center gap-1">
        <button
          :disabled="currentPage <= 1"
          class="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
          @click="currentPage--"
        >Prev</button>
        <span class="text-xs text-gray-400 px-1">{{ currentPage }} / {{ totalPages }}</span>
        <button
          :disabled="currentPage >= totalPages"
          class="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
          @click="currentPage++"
        >Next</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Download } from 'lucide-vue-next'
import type { TableWidgetConfig } from '~/types/dashboard'

const props = defineProps<{
  config: TableWidgetConfig
}>()

const sortKey = ref<string | null>(null)
const sortDir = ref<'asc' | 'desc'>('asc')
const currentPage = ref(1)
const columnFilters = ref<Record<string, string>>({})

const rowsPerPage = computed(() => props.config.rowsPerPage ?? 25)
const hasFilterableColumns = computed(() => props.config.columns.some(c => c.filterable))

function toggleSort(key: string) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

// Column filtering (client-side)
const filteredRows = computed(() => {
  let rows = props.config.rows
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
    const av = a[key]
    const bv = b[key]
    if (av == null) return 1
    if (bv == null) return -1
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir
    return String(av).localeCompare(String(bv)) * dir
  })
})

// Pagination
const totalPages = computed(() =>
  Math.max(1, Math.ceil(sortedRows.value.length / rowsPerPage.value)),
)

const displayRows = computed(() => {
  if (!props.config.pagination) return sortedRows.value
  const start = (currentPage.value - 1) * rowsPerPage.value
  return sortedRows.value.slice(start, start + rowsPerPage.value)
})

// Reset page when data or filters change
watch([() => props.config.rows, columnFilters], () => { currentPage.value = 1 }, { deep: true })

function formatCell(value: any, format?: string): string {
  if (value == null) return '—'
  switch (format) {
    case 'currency':
      return '$' + Number(value).toLocaleString()
    case 'number':
      return Number(value).toLocaleString()
    case 'percent':
      return (value > 0 ? '+' : '') + Number(value).toFixed(1) + '%'
    case 'date':
      return new Date(value).toLocaleDateString()
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
</script>
