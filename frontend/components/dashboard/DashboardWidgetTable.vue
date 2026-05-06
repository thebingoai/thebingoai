<template>
  <div
    class="flex h-full flex-col overflow-hidden"
    :style="containerStyle"
  >
    <div v-if="config.showTitle && config.title" class="flex-shrink-0 px-4 pt-3 pb-1">
      <span class="widget-label">{{ config.title }}</span>
    </div>

    <!-- Empty state: all columns are metrics with no dimensions -->
    <div v-if="isEmptyState" class="flex h-full items-center justify-center p-10 text-sm text-gray-400 text-center">
      Add at least one Dimension column to display grouped data.
    </div>

    <!-- Table wrapper: horizontal scroll is opt-in -->
    <div v-if="!isEmptyState" class="flex-1 overflow-auto" :class="config.horizontalScrolling ? 'overflow-x-auto' : ''">
      <table
        class="w-full"
        :class="fontClass"
        :style="config.fontColor ? { color: config.fontColor } : undefined"
      >

        <!-- Header -->
        <thead
          v-if="config.showHeader !== false"
          :style="config.headerBackground ? { background: config.headerBackground } : undefined"
          class="sticky top-0 bg-white border-b border-gray-100 dark:bg-neutral-800 dark:border-neutral-700"
        >
          <tr>
            <!-- Row number header -->
            <th
              v-if="config.showRowNumbers"
              class="px-3 py-2.5 text-left text-xs font-medium text-gray-300 uppercase tracking-wide w-8"
            >#</th>

            <th
              v-for="(col, i) in config.columns"
              :key="i"
              class="px-4 py-2.5 text-xs font-medium text-gray-400 uppercase tracking-wide dark:text-neutral-400"
              :class="[
                col.sortable ? 'cursor-pointer hover:text-gray-600 dark:hover:text-neutral-200 select-none' : '',
                colAlignClass(col),
                config.wrapText ? '' : 'whitespace-nowrap',
              ]"
              @click="col.sortable && toggleSort(i)"
            >
              <div
                class="flex items-center gap-1"
                :class="col.align === 'right' ? 'justify-end' : col.align === 'center' ? 'justify-center' : ''"
              >
                {{ col.label }}
                <span v-if="col.sortable && sortKey === i" class="text-gray-500 dark:text-neutral-400">
                  {{ sortDir === 'asc' ? '↑' : '↓' }}
                </span>
              </div>
            </th>
          </tr>

          <!-- Column filter row -->
          <tr v-if="hasFilterableColumns">
            <th v-if="config.showRowNumbers" />
            <th v-for="(col, i) in config.columns" :key="i" class="px-4 py-1">
              <input
                v-if="col.filterable"
                v-model="columnFilters[i]"
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
            :style="rowStyle(i)"
          >
            <!-- Row number cell -->
            <td
              v-if="config.showRowNumbers"
              class="px-3 py-2.5 text-[11px] text-gray-300 tabular-nums w-8 dark:text-neutral-600"
            >{{ rowOffset + i + 1 }}</td>

            <td
              v-for="(col, ci) in config.columns"
              :key="ci"
              class="px-4 py-2.5 dark:text-neutral-300"
              :class="[
                colAlignClass(col),
                config.wrapText ? '' : 'whitespace-nowrap',
                isNumericFormat(col) ? 'tabular-nums' : '',
              ]"
              :style="col.displayType === 'heatmap' ? heatmapCellStyle(row[ci], ci) : undefined"
            >
              <!-- Bar display -->
              <template v-if="col.displayType === 'bar' && row[ci] != null">
                <div class="flex items-center gap-2">
                  <div class="flex-1 h-2 rounded-full overflow-hidden" style="background:rgba(99,102,241,0.12);">
                    <div
                      class="h-full rounded-full transition-all"
                      :style="{
                        width: barWidth(row[ci], ci) + '%',
                        background: colColor(ci),
                      }"
                    />
                  </div>
                  <span v-if="col.showBarValue !== false" class="text-xs min-w-[40px] text-right">
                    {{ formatCell(row[ci], col) }}
                  </span>
                </div>
              </template>

              <!-- Default / number / heatmap text -->
              <template v-else>
                <span :class="getCellClass(row[ci], col.format)">
                  {{ formatCell(row[ci], col) }}
                </span>
              </template>
            </td>
          </tr>
        </tbody>

        <!-- Summary row -->
        <tfoot v-if="showSummaryFooter">
          <tr class="border-t-2 border-gray-200 bg-gray-50 dark:border-neutral-600 dark:bg-neutral-800">
            <td v-if="config.showRowNumbers" class="px-3 py-2.5 text-[11px] text-gray-300">Σ</td>
            <td
              v-for="(col, i) in config.columns"
              :key="i"
              class="px-4 py-2.5 text-xs font-semibold text-gray-700 dark:text-neutral-300"
              :class="[colAlignClass(col), isNumericFormat(col) ? 'tabular-nums' : '']"
            >
              {{ summaryValue(col, i) }}
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
const NUMERIC_FORMATS = new Set(['number', 'currency', 'percent', 'duration'])

const props = defineProps<{
  config: TableWidgetConfig
}>()

// sortKey is now a column position index, not a col.key string
const sortKey = ref<number | null>(null)
const sortDir = ref<'asc' | 'desc'>('asc')
const currentPage = ref(1)
// columnFilters keyed by column position index so duplicate-key columns get independent inputs
const columnFilters = ref<Record<number, string>>({})

onMounted(() => {
  if (props.config.defaultSortKey) {
    const idx = props.config.columns.findIndex(c => c.key === props.config.defaultSortKey)
    if (idx >= 0) {
      sortKey.value = idx
      sortDir.value = props.config.defaultSortDir ?? 'asc'
    }
  }
})

watch(
  () => [props.config.defaultSortKey, props.config.defaultSortDir] as const,
  ([key, dir]) => {
    if (key && sortKey.value === null) {
      const idx = props.config.columns.findIndex(c => c.key === key)
      if (idx >= 0) {
        sortKey.value = idx
        sortDir.value = dir ?? 'asc'
      }
    }
  },
)

const rowsPerPage = computed(() => props.config.rowsPerPage ?? 25)
const hasFilterableColumns = computed(() => props.config.columns.some(c => c.filterable))

function isNumericFormat(col: TableColumn): boolean {
  return NUMERIC_FORMATS.has(col.format ?? '')
}

function effectiveRole(col: TableColumn): 'dimension' | 'metric' {
  if (col.role) return col.role
  return isNumericFormat(col) ? 'metric' : 'dimension'
}

function defaultAgg(col: TableColumn): string {
  return isNumericFormat(col) ? 'sum' : 'count'
}

function aggregateColumn(rows: any[], col: TableColumn): any {
  const agg = col.aggregation && col.aggregation !== 'none' ? col.aggregation : defaultAgg(col)
  const allVals = rows.map(r => r[col.key])
  if (agg === 'count') return allVals.filter(v => v != null && v !== '').length
  if (agg === 'countDistinct') return new Set(allVals.filter(v => v != null && v !== '')).size
  // numeric aggregations
  const nums = allVals.map(v => Number(v)).filter(v => isFinite(v))
  if (!nums.length) return null
  switch (agg) {
    case 'sum': return nums.reduce((a, b) => a + b, 0)
    case 'average': return nums.reduce((a, b) => a + b, 0) / nums.length
    case 'min': return Math.min(...nums)
    case 'max': return Math.max(...nums)
    case 'median': {
      const s = [...nums].sort((a, b) => a - b)
      const m = Math.floor(s.length / 2)
      return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
    }
    case 'stdDev': {
      const mean = nums.reduce((a, b) => a + b, 0) / nums.length
      return Math.sqrt(nums.map(v => (v - mean) ** 2).reduce((a, b) => a + b, 0) / nums.length)
    }
    case 'variance': {
      const mean = nums.reduce((a, b) => a + b, 0) / nums.length
      return nums.map(v => (v - mean) ** 2).reduce((a, b) => a + b, 0) / nums.length
    }
    default: return allVals[0]
  }
}

// Convert a source row (keyed by col.key) to an index-keyed row so each column
// position reads independently even when two columns share the same source key.
function indexRow(row: Record<string, any>, cols: TableColumn[]): Record<number, any> {
  const out: Record<number, any> = {}
  for (let i = 0; i < cols.length; i++) out[i] = row[cols[i].key]
  return out
}

function colAlignClass(col: TableColumn): string {
  if (col.align === 'right') return 'text-right'
  if (col.align === 'center') return 'text-center'
  return 'text-left'
}

// columnColors is user-configured by source key; same-key columns intentionally share color
function colColor(colIndex: number): string {
  const col = props.config.columns[colIndex]
  return (col && props.config.columnColors?.[col.key]) ?? THEME_COLOR
}

// Show footer when the global toggle is on, OR when any numeric column has an
// explicit aggregation set (so users see the calc without hunting the toggle).
const showSummaryFooter = computed(() => {
  if (props.config.showSummaryRow) return true
  return props.config.columns.some(c =>
    isNumericFormat(c) && c.aggregation && c.aggregation !== 'none',
  )
})

const containerStyle = computed(() => {
  const style: Record<string, string> = {}
  if (props.config.borderWidth && props.config.borderWidth > 0) {
    const color = props.config.borderColor ?? '#e5e7eb'
    const styleVal = props.config.borderStyle ?? 'solid'
    style.border = `${props.config.borderWidth}px ${styleVal} ${color}`
  }
  if (props.config.borderRadius && props.config.borderRadius > 0) {
    style.borderRadius = `${props.config.borderRadius}px`
  }
  return style
})

const fontClass = computed(() => {
  const classes: string[] = []
  switch (props.config.fontFamily) {
    case 'sans': classes.push('font-sans'); break
    case 'serif': classes.push('font-serif'); break
    case 'mono': classes.push('font-mono'); break
  }
  switch (props.config.fontSize ?? 'sm') {
    case 'xs': classes.push('text-[11px]'); break
    case 'sm': classes.push('text-xs'); break
    case 'md': classes.push('text-[13px]'); break
    case 'lg': classes.push('text-sm'); break
  }
  return classes.join(' ')
})

function rowStyle(i: number): Record<string, string> {
  const style: Record<string, string> = {}
  if (props.config.oddRowColor && i % 2 === 0) style.background = props.config.oddRowColor
  if (props.config.evenRowColor && i % 2 === 1) style.background = props.config.evenRowColor
  if (props.config.cellBorderColor) style.borderTopColor = props.config.cellBorderColor
  return style
}

// Per-column max/min for bar width and heatmap intensity, keyed by column position index
const colMaxValues = computed(() => {
  const map: Record<number, number> = {}
  const cols = props.config.columns
  for (let i = 0; i < cols.length; i++) {
    const col = cols[i]
    if (col.displayType === 'bar' || col.displayType === 'heatmap') {
      const vals = (props.config.rows ?? [])
        .map(r => Number(r[col.key]))
        .filter(v => isFinite(v))
      map[i] = vals.length ? Math.max(...vals) : 0
    }
  }
  return map
})

const colMinValues = computed(() => {
  const map: Record<number, number> = {}
  const cols = props.config.columns
  for (let i = 0; i < cols.length; i++) {
    const col = cols[i]
    if (col.displayType === 'heatmap') {
      const vals = (props.config.rows ?? [])
        .map(r => Number(r[col.key]))
        .filter(v => isFinite(v))
      map[i] = vals.length ? Math.min(...vals) : 0
    }
  }
  return map
})

function barWidth(value: any, colIndex: number): number {
  const max = colMaxValues.value[colIndex]
  if (!max) return 0
  return Math.max(0, Math.min(100, (Number(value) / max) * 100))
}

function heatmapCellStyle(value: any, colIndex: number): Record<string, string> {
  if (value == null) return {}
  const min = colMinValues.value[colIndex] ?? 0
  const max = colMaxValues.value[colIndex] ?? 0
  const intensity = max === min ? 0.5 : Math.max(0, Math.min(1, (Number(value) - min) / (max - min)))
  const color = colColor(colIndex)
  const opacityHex = Math.round(intensity * 76 + 13).toString(16).padStart(2, '0')
  return { background: `${color}${opacityHex}` }
}

// Column stats for comparison calculations, keyed by column position index
const colStats = computed(() => {
  const stats: Record<number, { total: number; max: number }> = {}
  const cols = props.config.columns
  for (let i = 0; i < cols.length; i++) {
    const col = cols[i]
    if (!col.comparisonCalc || col.comparisonCalc === 'none') continue
    const vals = sortedRows.value.map(r => Number(r[i])).filter(v => isFinite(v))
    stats[i] = {
      total: vals.reduce((a, b) => a + b, 0),
      max: vals.length ? Math.max(...vals) : 0,
    }
  }
  return stats
})

// Running values — computed in sort order, before pagination, keyed by column position index
const runningValues = computed(() => {
  const result: Record<number, number[]> = {}
  const cols = props.config.columns
  for (let i = 0; i < cols.length; i++) {
    const col = cols[i]
    if (!col.runningCalc || col.runningCalc === 'none') continue
    let runSum = 0, runCount = 0, runMin = Infinity, runMax = -Infinity, prev: number | null = null
    result[i] = sortedRows.value.map((row) => {
      const v = isFinite(Number(row[i])) ? Number(row[i]) : 0
      runSum += v; runCount++
      runMin = Math.min(runMin, v); runMax = Math.max(runMax, v)
      let out: number
      switch (col.runningCalc) {
        case 'runningSum': out = runSum; break
        case 'runningMin': out = runMin; break
        case 'runningMax': out = runMax; break
        case 'runningCount': out = runCount; break
        case 'runningAverage': out = runSum / runCount; break
        case 'runningDelta': out = prev === null ? 0 : v - prev; break
        case 'runningPercentageDelta': out = prev === null || prev === 0 ? 0 : ((v - prev) / Math.abs(prev)) * 100; break
        default: out = v
      }
      prev = v
      return out
    })
  }
  return result
})

// Apply comparison + running transforms on top of sorted rows
const processedRows = computed(() => {
  const cols = props.config.columns
  const hasCalcs = cols.some(
    c => (c.comparisonCalc && c.comparisonCalc !== 'none') ||
         (c.runningCalc && c.runningCalc !== 'none'),
  )
  if (!hasCalcs) return sortedRows.value
  return sortedRows.value.map((row, rowIdx) => {
    const out: Record<number, any> = { ...row }
    for (let i = 0; i < cols.length; i++) {
      const col = cols[i]
      if (col.comparisonCalc && col.comparisonCalc !== 'none') {
        const stats = colStats.value[i]
        if (!stats) continue
        const v = Number(row[i])
        if (!isFinite(v)) continue
        switch (col.comparisonCalc) {
          case 'percentOfTotal': out[i] = stats.total ? (v / stats.total) * 100 : 0; break
          case 'diffFromTotal': out[i] = v - stats.total; break
          case 'percentDiffFromTotal': out[i] = stats.total ? ((v - stats.total) / Math.abs(stats.total)) * 100 : 0; break
          case 'percentOfMax': out[i] = stats.max ? (v / stats.max) * 100 : 0; break
          case 'diffFromMax': out[i] = v - stats.max; break
          case 'percentDiffFromMax': out[i] = stats.max ? ((v - stats.max) / Math.abs(stats.max)) * 100 : 0; break
        }
      }
      if (col.runningCalc && col.runningCalc !== 'none') {
        const vals = runningValues.value[i]
        if (vals) out[i] = vals[rowIdx]
      }
    }
    return out
  })
})

// Filtering on source rows (still keyed by col.key); filter input is per column position
const filteredRows = computed(() => {
  let rows = props.config.rows ?? []
  for (const [iStr, filterVal] of Object.entries(columnFilters.value)) {
    if (!filterVal) continue
    const col = props.config.columns[Number(iStr)]
    if (!col) continue
    const lower = filterVal.toLowerCase()
    rows = rows.filter(row => String(row[col.key] ?? '').toLowerCase().includes(lower))
  }
  return rows
})

// Dimension/Metric split (cached) — includes column position index
const dimensionCols = computed(() =>
  props.config.columns.map((c, i) => ({ col: c, i })).filter(({ col }) => effectiveRole(col) === 'dimension'),
)
const metricCols = computed(() =>
  props.config.columns.map((c, i) => ({ col: c, i })).filter(({ col }) => effectiveRole(col) === 'metric'),
)

// Empty-state signal: only metrics, no dimensions → can't group
const isEmptyState = computed(() => dimensionCols.value.length === 0 && metricCols.value.length > 0)

// Grouping: always group by every dimension. Output rows are index-keyed so same-source-key
// columns are written to distinct numeric slots without overwriting each other.
const groupedRows = computed((): Record<number, any>[] => {
  const dims = dimensionCols.value
  const metrics = metricCols.value
  const cols = props.config.columns

  // No dimensions: pass through raw rows converted to index-keyed form
  if (dims.length === 0) return filteredRows.value.map(r => indexRow(r, cols))

  const groups = new Map<string, { dimVals: any[]; rows: any[] }>()
  for (const row of filteredRows.value) {
    const groupKey = dims.map(({ col: d }) => String(row[d.key] ?? '')).join('\x00')
    let g = groups.get(groupKey)
    if (!g) {
      g = { dimVals: dims.map(({ col: d }) => row[d.key]), rows: [] }
      groups.set(groupKey, g)
    }
    g.rows.push(row)
  }

  return Array.from(groups.values()).map((group) => {
    const out: Record<number, any> = {}
    // Write dimension values at their column positions
    for (let di = 0; di < dims.length; di++) {
      out[dims[di].i] = group.dimVals[di]
    }
    // Write aggregated metric values at their column positions
    for (const { col: m, i: mi } of metrics) {
      out[mi] = aggregateColumn(group.rows, m)
    }
    return out
  })
})

// Sorting (operates on grouped index-keyed rows; sortKey is a column position index)
const sortedRows = computed(() => {
  if (sortKey.value === null) return groupedRows.value
  const sk = sortKey.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...groupedRows.value].sort((a, b) => {
    const av = a[sk]; const bv = b[sk]
    if (av == null) return 1
    if (bv == null) return -1
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir
    return String(av).localeCompare(String(bv)) * dir
  })
})

function toggleSort(colIndex: number) {
  if (sortKey.value === colIndex) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  }
  else {
    sortKey.value = colIndex
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
  if (!props.config.pagination) return processedRows.value
  return processedRows.value.slice(rowOffset.value, rowOffset.value + rowsPerPage.value)
})

watch([() => props.config.rows, columnFilters], () => { currentPage.value = 1 }, { deep: true })

// Summary row — col index needed to read from index-keyed sorted rows
function summaryValue(col: TableColumn, colIndex: number): string {
  if (!isNumericFormat(col)) return '—'
  if (col.aggregation === 'none') return '—'
  const vals = sortedRows.value
    .map(r => Number(r[colIndex]))
    .filter(v => isFinite(v))
  if (!vals.length) return missingValue()

  let result: number
  switch (col.aggregation ?? 'sum') {
    case 'sum': result = vals.reduce((a, b) => a + b, 0); break
    case 'average': result = vals.reduce((a, b) => a + b, 0) / vals.length; break
    case 'count': result = vals.length; break
    case 'countDistinct': result = new Set(vals).size; break
    case 'min': result = Math.min(...vals); break
    case 'max': result = Math.max(...vals); break
    case 'median': {
      const s = [...vals].sort((a, b) => a - b)
      const m = Math.floor(s.length / 2)
      result = s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
      break
    }
    case 'stdDev': {
      const mean = vals.reduce((a, b) => a + b, 0) / vals.length
      result = Math.sqrt(vals.map(v => (v - mean) ** 2).reduce((a, b) => a + b, 0) / vals.length)
      break
    }
    case 'variance': {
      const mean = vals.reduce((a, b) => a + b, 0) / vals.length
      result = vals.map(v => (v - mean) ** 2).reduce((a, b) => a + b, 0) / vals.length
      break
    }
    default: result = vals.reduce((a, b) => a + b, 0)
  }
  return formatCell(result, col)
}

// Cell formatting
function missingValue(): string {
  switch (props.config.missingDataDisplay) {
    case 'blank': return ''
    case 'noData': return 'No data'
    default: return '—'
  }
}

function formatCompact(num: number): string {
  const abs = Math.abs(num)
  if (abs >= 1e9) return (num / 1e9).toFixed(1).replace(/\.0$/, '') + 'B'
  if (abs >= 1e6) return (num / 1e6).toFixed(1).replace(/\.0$/, '') + 'M'
  if (abs >= 1e3) return (num / 1e3).toFixed(1).replace(/\.0$/, '') + 'K'
  return num.toLocaleString()
}

function formatCell(value: any, col: TableColumn): string {
  if (value == null) return missingValue()
  const num = Number(value)
  if (col.compactNumbers && isFinite(num) && NUMERIC_FORMATS.has(col.format ?? '')) {
    return formatCompact(num)
  }
  const dp = col.decimalPlaces ?? 2
  const round = !!col.roundValue
  switch (col.format) {
    case 'currency': {
      if (round) return '$' + num.toFixed(dp).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
      return '$' + num.toLocaleString()
    }
    case 'number': {
      if (round) return num.toFixed(dp).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
      return num.toLocaleString()
    }
    case 'percent': {
      const formatted = round ? num.toFixed(dp) : num.toFixed(1)
      return (num > 0 ? '+' : '') + formatted + '%'
    }
    case 'date':
      return parseUtcDate(value).toLocaleDateString()
    case 'duration': {
      const secs = Math.round(num)
      const h = Math.floor(secs / 3600)
      const m = Math.floor((secs % 3600) / 60)
      const s = secs % 60
      if (h > 0) return `${h}h ${m}m`
      if (m > 0) return `${m}m ${s}s`
      return `${s}s`
    }
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

// CSV export uses index-keyed sorted rows so each column position exports independently
function exportCsv() {
  const headers = props.config.columns.map(c => escapeCsvField(c.label))
  const rows = sortedRows.value.map(row =>
    props.config.columns.map((_, i) => escapeCsvField(String(row[i] ?? ''))).join(','),
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
