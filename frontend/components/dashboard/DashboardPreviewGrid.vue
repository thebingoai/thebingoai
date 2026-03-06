<template>
  <div ref="containerRef" class="relative w-full overflow-hidden rounded-t-lg bg-gray-50" style="height: 96px;">
    <template v-if="widgets.length > 0 && containerWidth > 0">
      <div
        v-for="(widget, i) in widgets"
        :key="i"
        class="absolute rounded overflow-hidden"
        :style="blockStyle(widget)"
      >
        <svg
          width="100%"
          height="100%"
          :viewBox="`0 0 60 40`"
          preserveAspectRatio="xMidYMid meet"
          xmlns="http://www.w3.org/2000/svg"
        >
          <!-- KPI widget illustration -->
          <template v-if="widget.type === 'kpi'">
            <rect x="6" y="8" width="20" height="3" rx="1.5" :fill="TYPE_STROKE.kpi" opacity="0.5" />
            <text x="6" y="26" font-size="12" font-weight="700" :fill="TYPE_STROKE.kpi" font-family="sans-serif">42</text>
            <!-- trend arrow up -->
            <polyline points="38,28 42,22 46,28" :stroke="TYPE_STROKE.kpi" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round" />
            <line x1="42" y1="22" x2="42" y2="32" :stroke="TYPE_STROKE.kpi" stroke-width="1.5" stroke-linecap="round" />
          </template>

          <!-- Bar chart illustration -->
          <template v-else-if="widget.type === 'chart' && (!widget.chartType || widget.chartType === 'bar')">
            <rect x="6"  y="28" width="7" height="8"  rx="1" :fill="TYPE_STROKE.chart" opacity="0.7" />
            <rect x="15" y="20" width="7" height="16" rx="1" :fill="TYPE_STROKE.chart" opacity="0.8" />
            <rect x="24" y="24" width="7" height="12" rx="1" :fill="TYPE_STROKE.chart" opacity="0.7" />
            <rect x="33" y="16" width="7" height="20" rx="1" :fill="TYPE_STROKE.chart" opacity="0.9" />
            <rect x="42" y="22" width="7" height="14" rx="1" :fill="TYPE_STROKE.chart" opacity="0.75" />
            <line x1="4" y1="36" x2="52" y2="36" :stroke="TYPE_STROKE.chart" stroke-width="1" opacity="0.4" />
          </template>

          <!-- Line / Area chart illustration -->
          <template v-else-if="widget.type === 'chart' && (widget.chartType === 'line' || widget.chartType === 'area')">
            <template v-if="widget.chartType === 'area'">
              <path d="M6,30 C14,24 20,28 28,18 C36,8 44,22 54,16 L54,36 L6,36 Z" :fill="TYPE_STROKE.chart" opacity="0.2" />
            </template>
            <path d="M6,30 C14,24 20,28 28,18 C36,8 44,22 54,16" :stroke="TYPE_STROKE.chart" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" opacity="0.9" />
            <line x1="4" y1="36" x2="56" y2="36" :stroke="TYPE_STROKE.chart" stroke-width="1" opacity="0.4" />
          </template>

          <!-- Pie chart illustration -->
          <template v-else-if="widget.type === 'chart' && widget.chartType === 'pie'">
            <circle cx="30" cy="22" r="14" fill="#f0fdf4" :stroke="TYPE_STROKE.chart" stroke-width="0.5" />
            <path d="M30,22 L30,8 A14,14 0 0,1 44,22 Z" :fill="TYPE_STROKE.chart" opacity="0.9" />
            <path d="M30,22 L44,22 A14,14 0 0,1 23,35 Z" fill="#6ee7b7" opacity="0.7" />
            <path d="M30,22 L23,35 A14,14 0 0,1 30,8 Z" fill="#34d399" opacity="0.5" />
          </template>

          <!-- Doughnut chart illustration -->
          <template v-else-if="widget.type === 'chart' && widget.chartType === 'doughnut'">
            <path d="M30,10 A12,12 0 0,1 42,22" :stroke="TYPE_STROKE.chart" stroke-width="6" fill="none" stroke-linecap="butt" opacity="0.9" />
            <path d="M42,22 A12,12 0 0,1 26,33" stroke="#6ee7b7" stroke-width="6" fill="none" stroke-linecap="butt" opacity="0.7" />
            <path d="M26,33 A12,12 0 0,1 30,10" stroke="#34d399" stroke-width="6" fill="none" stroke-linecap="butt" opacity="0.5" />
            <circle cx="30" cy="22" r="6" fill="#f0fdf4" />
          </template>

          <!-- Scatter chart illustration -->
          <template v-else-if="widget.type === 'chart' && widget.chartType === 'scatter'">
            <circle cx="12" cy="28" r="2.5" :fill="TYPE_STROKE.chart" opacity="0.8" />
            <circle cx="20" cy="20" r="2.5" :fill="TYPE_STROKE.chart" opacity="0.8" />
            <circle cx="28" cy="14" r="2.5" :fill="TYPE_STROKE.chart" opacity="0.8" />
            <circle cx="36" cy="26" r="2.5" :fill="TYPE_STROKE.chart" opacity="0.8" />
            <circle cx="44" cy="18" r="2.5" :fill="TYPE_STROKE.chart" opacity="0.8" />
            <circle cx="16" cy="32" r="2.5" :fill="TYPE_STROKE.chart" opacity="0.8" />
            <line x1="4" y1="36" x2="56" y2="36" :stroke="TYPE_STROKE.chart" stroke-width="1" opacity="0.4" />
          </template>

          <!-- Table widget illustration -->
          <template v-else-if="widget.type === 'table'">
            <rect x="4" y="6" width="52" height="7" rx="1.5" :fill="TYPE_STROKE.table" opacity="0.6" />
            <rect x="4" y="16" width="52" height="4" rx="1" :fill="TYPE_STROKE.table" opacity="0.25" />
            <rect x="4" y="23" width="52" height="4" rx="1" :fill="TYPE_STROKE.table" opacity="0.2" />
            <rect x="4" y="30" width="52" height="4" rx="1" :fill="TYPE_STROKE.table" opacity="0.25" />
          </template>

          <!-- Text widget illustration -->
          <template v-else-if="widget.type === 'text'">
            <rect x="6" y="8"  width="48" height="3" rx="1.5" :fill="TYPE_STROKE.text" opacity="0.5" />
            <rect x="6" y="15" width="44" height="3" rx="1.5" :fill="TYPE_STROKE.text" opacity="0.4" />
            <rect x="6" y="22" width="40" height="3" rx="1.5" :fill="TYPE_STROKE.text" opacity="0.4" />
            <rect x="6" y="29" width="30" height="3" rx="1.5" :fill="TYPE_STROKE.text" opacity="0.3" />
          </template>

          <!-- Filter widget illustration -->
          <template v-else-if="widget.type === 'filter'">
            <rect x="4"  y="14" width="10" height="12" rx="6" :fill="TYPE_STROKE.filter" opacity="0.3" :stroke="TYPE_STROKE.filter" stroke-width="1" />
            <rect x="17" y="14" width="18" height="12" rx="6" :fill="TYPE_STROKE.filter" opacity="0.6" :stroke="TYPE_STROKE.filter" stroke-width="1" />
            <rect x="38" y="14" width="18" height="12" rx="6" :fill="TYPE_STROKE.filter" opacity="0.3" :stroke="TYPE_STROKE.filter" stroke-width="1" />
          </template>
        </svg>
      </div>
    </template>
    <div v-else class="flex h-full items-center justify-center">
      <span class="text-[10px] text-gray-300">No widgets</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { WidgetType, GridPosition } from '~/types/dashboard'
import type { ChartType } from '~/types/chart'

const props = defineProps<{
  widgets: { type: WidgetType; position: GridPosition; chartType?: ChartType }[]
}>()

const containerRef = ref<HTMLElement | null>(null)
const containerWidth = ref(0)

const COLS = 12
const ROW_HEIGHT = 10 // px per grid unit
const GAP = 2 // px gap between blocks

const TYPE_STROKE: Record<WidgetType, string> = {
  kpi:    '#3b82f6', // blue-500
  chart:  '#22c55e', // green-500
  table:  '#eab308', // yellow-500
  text:   '#9ca3af', // gray-400
  filter: '#ec4899', // pink-500
}

function blockStyle(widget: { type: WidgetType; position: GridPosition }) {
  const colWidth = containerWidth.value / COLS
  const { x, y, w, h } = widget.position
  return {
    left:   `${x * colWidth + GAP}px`,
    top:    `${y * ROW_HEIGHT + GAP}px`,
    width:  `${w * colWidth - GAP * 2}px`,
    height: `${h * ROW_HEIGHT - GAP * 2}px`,
    border: '1px solid #e5e7eb',
  }
}

onMounted(() => {
  if (!containerRef.value) return
  const ro = new ResizeObserver(entries => {
    containerWidth.value = entries[0]?.contentRect.width ?? 0
  })
  ro.observe(containerRef.value)
  containerWidth.value = containerRef.value.offsetWidth
  onUnmounted(() => ro.disconnect())
})
</script>
